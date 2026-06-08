"""Global Pydantic settings config (example placeholders)."""
from pydantic import BaseSettings


class EnvSpec(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    # Add additional configuration parameters as needed


settings = EnvSpec()
