from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Stock News API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./data/news.db"
    SCHEDULER_DB_URL: str = "sqlite:///./data/scheduler.db"

    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL_ANALYSIS: str = "llama3.1"
    OLLAMA_MODEL_NER: str = "llama3.1"
    OLLAMA_MODEL_WHISPER: str = "whisper"
    OLLAMA_TIMEOUT: int = 300  # seconds

    # Processing
    MAX_CONCURRENT_FETCHES: int = 3
    DATA_RETENTION_DAYS: int = 30
    AUTO_DISABLE_THRESHOLD: int = 5
    GLOBAL_PAUSE: bool = False

    # Paths
    DOWNLOADS_DIR: str = "./downloads"
    DATA_DIR: str = "./data"

    # CORS (for local development)
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
