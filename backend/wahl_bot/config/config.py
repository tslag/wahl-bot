"""Application settings loaded from environment for the Wahl-bot backend.

This module defines the :class:`Settings` model (based on Pydantic's
``BaseSettings``) and instantiates ``settings`` which is imported across
the application to access configuration values.

Notable fields include embedding/model keys, program storage paths,
database connection URL and JWT configuration for auth tokens.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Environment-backed application settings.

    Attributes:
        GROQ_API_KEY: API key for GROQ LLM provider.
        PROMPT_TEMPLATE_PATH_FEWSHOT: Path to few-shot prompt template.
        PROMPT_TEMPLATE_PATH_QA: Path to QA prompt template.
        PROMPT_TEMPLATE_PATH_QUERY_OPT: Path to query optimization template.
        PROGRAM_DIRECTORY: Filesystem directory where uploaded programs are stored.
        DATABASE_URL_ASYNC: Async database URL for SQLAlchemy.

        SECRET_KEY: JWT signing secret.
        ALGORITHM: JWT signing algorithm.
        ACCESS_TOKEN_EXPIRE_MINUTES: Access token lifetime in minutes.
        REFRESH_TOKEN_EXPIRE_DAYS: Refresh token lifetime in days.
    """

    GROQ_API_KEY: str
    PROMPT_TEMPLATE_PATH_FEWSHOT: str
    PROMPT_TEMPLATE_PATH_QA: str
    PROMPT_TEMPLATE_PATH_QUERY_OPT: str

    PROGRAM_DIRECTORY: str

    DATABASE_URL_ASYNC: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()
