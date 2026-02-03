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
    def __init__(self, **kwargs) -> None:
        self.program_name = kwargs["program_name"]
        self.program_store = ProgramStore()

        # embeddings model with 384 dimensions
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            # model_kwargs={'device': 'cpu'}
        )

        self.vector_store_table = "documents"
        self.similarity_search_threshold = (
            0.4  # equivalent to 70% similarity due to cosine distance range
        )
        self.similarity_search_limit = 5

    async def create_index_for_program(self):
        logger.info("Creating index documents for program %s", self.program_name)
        if not await self.check_existence_for_program_documents():
            documents = self.load_program_pages()
            # Extract content for batch embedding
            docs_content = [doc.content for doc in documents]

            # Generate all embeddings in one batch call
            embeddings = await self.get_embeddings_batch(docs_content)

            await self.create_documents_batch(
                documents_data=documents, embeddings=embeddings
            )

        return True

    async def check_existence_for_program_documents(self) -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Document.id)
                .where(Document.program_name == self.program_name)
                .limit(1)
            )
            doc_id = result.scalar_one_or_none()
            return doc_id is not None

    def load_program_pages(self) -> List[DocumentCreate]:
        # Get absolute path to program directory
        file_path = self.program_store.program_dir / f"{self.program_name}.pdf"

        # Ensure file exists
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
            page.page_content = "\n".join(page.page_content.splitlines())
            documents.append(document)
        return documents

    async def get_embedding(self, text: str) -> List[float]:
        return await self.embeddings.aembed_query(text)

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return await self.embeddings.aembed_documents(texts)

    async def create_documents_batch(
        self, documents_data: List[DocumentCreate], embeddings: List[List[float]]
    ) -> bool:
        """Efficiently create multiple documents with embeddings in batch."""

        async with AsyncSessionLocal() as db:
            # Create Document objects with their embeddings
            db_documents = []
            for doc_data, embedding in zip(documents_data, embeddings):
                db_document = Document(
                    program_name=doc_data.program_name,
                    page=doc_data.page,
                    content=doc_data.content,
                    embedding=embedding,
                )
                db_documents.append(db_document)

            # Bulk insert all documents at once
            db.add_all(db_documents)
            await db.commit()

        return True

    async def delete_index_for_program(self) -> bool:
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
        query_embedding = await self.get_embedding(query)

        # Prefilter by program_name

        # Use SQLAlchemy to prefilter by program_name, compute similarity as
        # 1 - l2_distance(query_embedding), apply threshold, order by l2
        # distance (ascending) and limit results.
        async with AsyncSessionLocal() as db:
            stmt = (
                select(
                    Document,
                    # cosine_distance e [0,2] => similarity in [1,-1], where 1 is most similar
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

            # rows are tuples (Document, similarity)
            documents = []
            for doc, similarity in rows:
                documents.append((doc, similarity))

        return documents
