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
    OLLAMA_TIMEOUT: int = 600  # seconds (increased for longer content processing)

    # Processing
    MAX_CONCURRENT_FETCHES: int = 3
    MAX_ARTICLES_PER_SOURCE: int = 20
    DATA_RETENTION_DAYS: int = 180
    YOUTUBE_MAX_VIDEO_AGE_DAYS: int = 2
    YOUTUBE_PLAYWRIGHT_FALLBACK: bool = True
    AUTO_DISABLE_THRESHOLD: int = 5
    GLOBAL_PAUSE: bool = False

    # LLM Content Limits
    LLM_MAX_CONTENT_CHARS: int = 30000   # Max chars of content sent to LLM (was hardcoded 8000)
    LLM_NUM_CTX: int = 16384             # Ollama context window (tokens) — increase for longer content

    # Paths
    DOWNLOADS_DIR: str = "./downloads"
    DATA_DIR: str = "./data"

    # Scraping / Anti-Bot
    BROWSER_ENGINE: str = "chromium"          # "chromium", "firefox", or "webkit"
    STEALTH_ENABLED: bool = True
    HUMAN_BEHAVIOR_ENABLED: bool = True
    USER_AGENT_ROTATION: bool = True

    # Proxy (optional)
    PROXY_URL: Optional[str] = None
    PROXY_USERNAME: Optional[str] = None
    PROXY_PASSWORD: Optional[str] = None
    PROXY_URLS: Optional[str] = None         # Comma-separated for rotation

    # RSS
    RSS_ENABLED: bool = True
    RSS_REQUEST_TIMEOUT: int = 30

    # Cloudflare Bypass
    CLOUDFLARE_BYPASS_ENABLED: bool = True    # Master switch for Cloudflare bypass
    NODRIVER_ENABLED: bool = True             # Enable nodriver (Tier 2) fallback
    NODRIVER_HEADLESS: bool = True            # Run nodriver Chrome headless
    NODRIVER_TIMEOUT: int = 45                # Seconds to wait for challenge resolution
    CURL_CFFI_IMPERSONATE: str = "chrome131"  # Browser to impersonate in TLS fingerprint
    CF_COOKIE_TTL_SECONDS: int = 900          # 15 min cache for cf_clearance cookies

    # CORS (for local development)
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
