from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    llm_model_name: str
    llm_base_url: str
    
    # Neue Multiprocessing & Storage Config
    data_dir: str = "data"
    max_workers: int = 12  # Reserviert 12 Kerne deines Threadrippers für RAG
    
    max_retries: int = 3
    debug_mode: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    return AppConfig()