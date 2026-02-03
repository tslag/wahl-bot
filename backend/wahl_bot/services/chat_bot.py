"""ChatBot service used to run RAG queries and generate answers for programs.

This module provides a lightweight wrapper around an LLM and a vector
store to perform retrieval-augmented generation (RAG) for program-specific
question-answering.
"""

from typing import List

from config.config import settings
from core.config_helper import get_prompt
from core.logging import logger
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document as LangChainDocument
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from services.doc_ingestion.vector_store import VectorStore


class ChatBot:
    """Orchestrates retrieval and language model calls to answer questions.

    Attributes:
        program_name: The program identifier this bot serves.
        llm: The language model client instance.
        vector_store: The vector search index for the program.
    """

    def __init__(self, **kwargs) -> None:
        self.program_name = kwargs["program_name"]

        self.llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model_name="openai/gpt-oss-120b",  # "llama-3.3-70b-versatile",
            temperature=0,
        )

        self.vector_store = VectorStore(program_name=self.program_name)
        logger.info("ChatBot initialized for program=%s", self.program_name)

    def setup_qa_chain(self) -> None:
        """Validate that the QA chain prerequisites are available.

        Raises:
            ValueError: If the vector store has not been initialized.
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Ingest documents first.")

    async def run_until_final_call(self, history: List[dict]):
        """Run the retrieval + generation flow and return the final answer.

        Args:
            history: Chat message history; expects the last entry to be the
                current user question and earlier entries to be previous turns.

        Returns:
            The final model-generated answer (string or structured content,
            depending on the underlying LLM chain response).

        Raises:
            IndexError: If `history` is empty.
        """

        logger.debug("Running chat RAG flow for program=%s", self.program_name)

        # NOTE: Build an optimized retrieval query from the user's last question
        # and the preceding chat history to improve semantic search results.
        last_question: str = history[-1].content
        chat_history: List[dict] = history[:-1]

        # NOTE: Map incoming message roles to the prompt system's expected roles.
        conversation_list: List[tuple[str, str]] | List = []
        for message in chat_history:
            if message.role == "user":
                role = "human"
            elif message.role == "assistant":
                role = "ai"
            conversation_list.append((role, message.content))

        opt_prompt_template = get_prompt(settings.PROMPT_TEMPLATE_PATH_QUERY_OPT)

        template = ChatPromptTemplate(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder("chat_history"),
                ("human", "{user_input}"),
            ]
        )

        prompt_value = {
            "system_prompt": opt_prompt_template,
            "chat_history": conversation_list,
            "user_input": last_question,
        }

        output_parser = StrOutputParser()
        query_opt_chain = template | self.llm | output_parser
        opt_query = await query_opt_chain.ainvoke(prompt_value)
        logger.debug("Optimized query generated: %s", opt_query)

        # NOTE: Use the optimized query to retrieve the most relevant documents
        # from the program's vector index.
        results = await self.vector_store.similarity_search(opt_query)
        logger.debug("Retrieved %d matching documents from vector store", len(results))

        docs = [
            LangChainDocument(
                page_content=doc.content,
                metadata={"page": doc.page, "similarity": similarity},
            )
            for doc, similarity in results
        ]

        # NOTE: Build the final prompt using the retrieved context and ask the
        # LLM to produce a concise, context-aware answer.
        qa_prompt_template = get_prompt(settings.PROMPT_TEMPLATE_PATH_QA)

        template = ChatPromptTemplate.from_messages(
            [
                ("system", qa_prompt_template),
                ("human", "{query}"),
            ]
        )

        stuff_chain = create_stuff_documents_chain(self.llm, template)
        final_answer = await stuff_chain.ainvoke(
            {
                "context": docs,
                "query": opt_query,
            }
        )
        logger.info("Generated final answer for program=%s", self.program_name)
        return final_answer

    async def chat_without_streaming(self, messages: List[dict]):
        """Run the chat flow and return the complete answer in one response.

        This convenience wrapper invokes the full RAG flow and packages the
        result into the same message shape consumed by the frontend.

        Args:
            messages: Chat history including the current user question.

        Returns:
            A dict with a single `message` entry containing the assistant's
            content and role.
        """
        chat_completion_response = await self.run_until_final_call(history=messages)

        return {"message": {"content": chat_completion_response, "role": "assistant"}}
