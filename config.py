from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Server
    APP_NAME: str = "WebSocket Messaging Server"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Message History
    MESSAGE_HISTORY_LIMIT: int = 100
    MESSAGE_RETENTION_DAYS: int = 30
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()