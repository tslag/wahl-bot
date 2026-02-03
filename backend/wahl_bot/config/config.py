from pathlib import Path

from pydantic_settings import BaseSettings

# Get the absolute path to the wahlbot_backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    GROQ_API_KEY: str
    PROMPT_TEMPLATE_PATH_FEWSHOT: str
    PROMPT_TEMPLATE_PATH_QA: str
    PROMPT_TEMPLATE_PATH_QUERY_OPT: str

    PROGRAM_DIRECTORY: str

    DATABASE_URL_ASYNC: str

    # JWT Configuration
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()
