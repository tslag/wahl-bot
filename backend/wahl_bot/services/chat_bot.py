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
    def __init__(self, **kwargs) -> None:
        self.program_name = kwargs["program_name"]

        self.llm = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model_name="openai/gpt-oss-120b",  # "llama-3.3-70b-versatile",
            temperature=0,
        )

        self.vector_store = VectorStore(program_name=self.program_name)
        logger.info("ChatBot initialized for program=%s", self.program_name)

    def setup_qa_chain(self):
        """Set up the QA chain for simple question-answering."""
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Ingest documents first.")

    async def run_until_final_call(self, history: List[dict]):
        """
        Description:
            Function to orchestrate RAG process.
        Parameters:
            history List[dict]: List of messsages of chat history
        Returns:
            chat_completion_coroutine Coroutine: Coroutine for final response from chat bot
        """

        logger.debug("Running chat RAG flow for program=%s", self.program_name)
        # STEP 1: Generate an optimized keyword search query based on the chat history and the last question

        last_question: str = history[-1].content
        chat_history: List[dict] = history[:-1]

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

        # STEP 2: Retrieve relevant documents from the search index with the GPT optimized query
        results = await self.vector_store.similarity_search(opt_query)
        logger.debug("Retrieved %d matching documents from vector store", len(results))

        docs = [
            LangChainDocument(
                page_content=doc.content,
                metadata={"page": doc.page, "similarity": similarity},
            )
            for doc, similarity in results
        ]

        # STEP 3: Generate a contextual and content specific answer using the search results and chat history

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
        """
        Description:
            Function to run and await chat process without streaming.
        Parameters:
            messages List[dict]: List of messsages of chat history
        Returns:
            chat_completion_response dict: Final response from chat bot
        """
        chat_completion_response = await self.run_until_final_call(history=messages)

        return {"message": {"content": chat_completion_response, "role": "assistant"}}
