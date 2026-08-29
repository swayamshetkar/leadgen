from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./leadgen.db"
    PROXY_URL: Optional[str] = None
    
    REQUEST_TIMEOUT: int = 20
    SEARCH_REQUEST_TIMEOUT: int = 5
    MAX_SEARCH_QUERIES_PER_LOCATION: int = 2
    MAX_DORK_QUERIES_PER_LOCATION: int = 1
    MAX_WEBSITE_DOMAINS_PER_JOB: int = 10
    SOURCE_TIMEOUT: int = 30
    WEBSITE_CRAWL_TIMEOUT: int = 15
    CRAWL_CONCURRENCY: int = 5
    MAX_CRAWL_DEPTH: int = 2
    
    # Delay between search requests to respect rate limits
    SEARCH_DELAY_MIN: float = 1.0
    SEARCH_DELAY_MAX: float = 2.5
    
    # Maximum pages crawled per website candidate
    MAX_PAGES_PER_DOMAIN: int = 6
    
    # User agent
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 LeadDiscoveryEngine/1.0"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
