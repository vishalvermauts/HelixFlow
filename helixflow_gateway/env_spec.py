from pydantic_settings import BaseSettings
from pydantic import Field


class EnvSpec(BaseSettings):
    # Infrastructure configuration mappings
    REDIS_DSN: str = Field(default="redis://localhost:6379/0", env="REDIS_DSN")
    CACHE_POOL_LIMIT: int = Field(default=100, env="CACHE_POOL_LIMIT")
    UPSTREAM_TIMEOUT_SEC: float = Field(default=120.0, env="UPSTREAM_TIMEOUT_SEC")
    DEFAULT_FABRIC_URL: str = Field(default="https://api.openai.com/v1", env="DEFAULT_FABRIC_URL")
    DEEPSEEK_API_KEY: str = Field(default="", env="DEEPSEEK_API_KEY")
    DEEPSEEK_API_BASE: str = Field(default="https://api.deepseek.com/v1", env="DEEPSEEK_API_BASE")
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    GEMINI_API_BASE: str = Field(default="https://generativelanguage.googleapis.com/v1beta", env="GEMINI_API_BASE")

    class Config:
        env_file = ".env"
        extra = "ignore"


runtime_settings = EnvSpec()
