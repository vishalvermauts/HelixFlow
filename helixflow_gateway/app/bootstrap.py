"""FastAPI engine setup, uvloop policy, & lifespan hooks."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(title="helixflow_gateway")

    # Import routers lazily to avoid circular imports
    try:
        from .controllers import execution, diagnostics  # noqa: F401
    except Exception:
        pass

    return app
