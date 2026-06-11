import asyncio
from fastapi import FastAPI
import redis.asyncio as aioredis
from helixflow_gateway.env_spec import runtime_settings
from helixflow_gateway.interceptors.security import TokenGuardInterceptor
from helixflow_gateway.controllers import diagnostics, execution, dashboard
from fastapi.staticfiles import StaticFiles

# Enforce uvloop if available for low-latency event loop
try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


def create_app() -> FastAPI:
    app = FastAPI(title="HelixFlow Gateway", version="1.0.0")

    @app.on_event("startup")
    async def startup_event():
        app.state.cache_pool = aioredis.ConnectionPool.from_url(
            runtime_settings.REDIS_DSN,
            max_connections=runtime_settings.CACHE_POOL_LIMIT,
            decode_responses=True,
        )
        app.state.cache_layer = aioredis.Redis(connection_pool=app.state.cache_pool)

    @app.on_event("shutdown")
    async def shutdown_event():
        try:
            await app.state.cache_pool.disconnect()
        except Exception:
            pass

    # Attach routers
    app.include_router(diagnostics.router)
    app.include_router(execution.router)
    app.include_router(dashboard.router)

    # Mount static assets for Dashboard SPA
    app.mount("/dashboard", StaticFiles(directory="helixflow_gateway/static", html=True), name="static")

    # Bind security filter interceptors into backend paths
    app.add_middleware(TokenGuardInterceptor)

    return app
