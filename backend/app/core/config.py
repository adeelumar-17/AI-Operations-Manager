'''
what the file does?
This module loads and validates global application configuration settings from environment variables and `.env` using Pydantic Settings, providing the singleton `settings` instance.

Classes:
    Settings: Application settings schema defining database connection strings, embedding configurations, and Groq LLM options.

Methods:
    resolve_database_host: Validator adjusting Docker container hostnames to localhost when running outside container networks.
'''

import socket
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def resolve_database_host(cls, v: str) -> str:
        """If host is 'db' (Docker network) but host machine cannot resolve it, fallback to 'localhost'."""
        if "@db:" in v or "@db/" in v:
            try:
                socket.gethostbyname("db")
            except (socket.gaierror, OSError):
                return v.replace("@db:", "@localhost:").replace("@db/", "@localhost/")
        return v

    # Embedding backend: 'sentence-transformers' (local, free) | 'openai'
    EMBEDDING_BACKEND: str = "sentence-transformers"
    SENTENCE_TRANSFORMERS_MODEL: str = "all-MiniLM-L6-v2"  # 384 dims

    # Groq LLM (for agent graph nodes and completions)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TEMPERATURE: float = 1.0
    GROQ_MAX_TOKENS: int = 2048
    GROQ_REASONING_EFFORT: str = "medium"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
