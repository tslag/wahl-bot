"""Vector store helpers: load, embed and query program documents.

This module wraps embedding generation and DB-backed vector search for
program-specific documents. It intentionally keeps the DB model and
vector logic co-located so the service can perform efficient prefiltering
and similarity calculations using SQL constructs.
"""

from typing import List

from core.logging import logger
from db.session import AsyncSessionLocal
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from models.programs import Document
from schemas.documents import DocumentCreate
from services.doc_ingestion.program_store import ProgramStore
from sqlalchemy import select, text


class VectorStore:
    """Encapsulates embedding generation and similarity search.

    Attributes:
        program_name: Identifier for the program this store serves.
        program_store: Helper to access program storage and files.
        embeddings: Embedding model instance with async APIs.
        vector_store_table: DB table used for storing documents.
        similarity_search_threshold: Minimum similarity score to include results.
        similarity_search_limit: Maximum number of results to return.
    """

    def __init__(self, **kwargs) -> None:
        """Initialize the `VectorStore` for a given program.

        Args:
            kwargs: Expects `program_name` as a keyword argument.
        """
        self.program_name = kwargs["program_name"]
        self.program_store = ProgramStore()

        # NOTE: Use a compact model with 384-dimension embeddings to keep
        # storage and query costs reasonable while retaining semantic fidelity.
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
        )

        self.vector_store_table = "documents"
        # NOTE: Threshold (60%) chosen empirically to filter low-similarity results.
        self.similarity_search_threshold = 0.2
        self.similarity_search_limit = 5

    async def create_index_for_program(self) -> bool:
        """Create embeddings and persist documents for the program.

        Returns:
            True when indexing completes or if documents already exist.
        """
        logger.info("Creating index documents for program %s", self.program_name)
        if not await self.check_existence_for_program_documents():
            documents = self.load_program_pages()
            # NOTE: Extract plain text content for batch embedding.
            docs_content = [doc.content for doc in documents]

            # NOTE: Generate embeddings in one batch call for efficiency.
            embeddings = await self.get_embeddings_batch(docs_content)

            await self.create_documents_batch(
                documents_data=documents, embeddings=embeddings
            )

        return True

    async def check_existence_for_program_documents(self) -> bool:
        """Return True if at least one document exists for the program."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Document.id)
                .where(Document.program_name == self.program_name)
                .limit(1)
            )
            doc_id = result.scalar_one_or_none()
            return doc_id is not None

    def load_program_pages(self) -> List[DocumentCreate]:
        """Load PDF pages for the program and convert them into schema objects.

        Returns:
            A list of `DocumentCreate` instances, one per PDF page.
        """
        file_path = self.program_store.program_dir / f"{self.program_name}.pdf"

        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        loader = PyPDFLoader(str(file_path))
        documents = []
        for page in loader.lazy_load():
            document = DocumentCreate(
                program_name=self.program_name,
                page=page.metadata["page_label"],
                content="\n".join(page.page_content.splitlines()),
            )
            # NOTE: Normalize page content newlines to keep embedding inputs stable.
            page.page_content = "\n".join(page.page_content.splitlines())
            documents.append(document)
        return documents

    async def get_embedding(self, text: str) -> List[float]:
        """Return an embedding vector for `text` using the async model API."""
        return await self.embeddings.aembed_query(text)

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for a batch of texts."""
        return await self.embeddings.aembed_documents(texts)

    async def create_documents_batch(
        self, documents_data: List[DocumentCreate], embeddings: List[List[float]]
    ) -> bool:
        """Persist a batch of documents and their embeddings into the DB.

        Args:
            documents_data: List of `DocumentCreate` objects.
            embeddings: Parallel list of embedding vectors.

        Returns:
            True on successful insertion.
        """

        async with AsyncSessionLocal() as db:
            db_documents = []
            for doc_data, embedding in zip(documents_data, embeddings):
                db_document = Document(
                    program_name=doc_data.program_name,
                    page=doc_data.page,
                    content=doc_data.content,
                    embedding=embedding,
                )
                db_documents.append(db_document)

            # NOTE: Bulk insert all documents at once for performance.
            db.add_all(db_documents)
            await db.commit()

        return True

    async def delete_index_for_program(self) -> bool:
        """Delete all document rows belonging to the program."""
        logger.info("Deleting vector store index for program %s", self.program_name)
        stmt = text("DELETE FROM documents WHERE program_name = :program_name")

        async with AsyncSessionLocal() as db:
            await db.execute(stmt, {"program_name": self.program_name})
            await db.commit()

        return True

    async def similarity_search(
        self,
        query: str,
    ) -> List[Document]:
        """Find and return documents similar to `query`.

        The method computes a query embedding and uses SQL to prefilter by
        `program_name`, compute similarity via `1 - cosine_distance`, apply the
        configured threshold, and return the top results ordered by distance.

        Args:
            query: Free-text query to search for.

        Returns:
            A list of tuples `(Document, similarity)` where `similarity` is a
            float with higher values indicating greater similarity.
        """
        query_embedding = await self.get_embedding(query)

        async with AsyncSessionLocal() as db:
            stmt = (
                select(
                    Document,
                    # NOTE: cosine_distance e [0,2] => similarity in [1,-1], where 1 is most similar
                    (1 - Document.embedding.cosine_distance(query_embedding)).label(
                        "similarity"
                    ),
                )
                .where(
                    Document.program_name == self.program_name,
                    (1 - Document.embedding.cosine_distance(query_embedding))
                    > self.similarity_search_threshold,
                )
                .order_by(Document.embedding.cosine_distance(query_embedding))
                .limit(self.similarity_search_limit)
            )

            result = await db.execute(stmt)
            rows = result.all()

            documents = []
            for doc, similarity in rows:
                documents.append((doc, similarity))

        return documents
