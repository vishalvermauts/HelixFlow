from fastapi.responses import JSONResponse
import hashlib
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis


class TokenGuardInterceptor(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Exclude metric loop paths and static dashboard paths from explicit verification cycles
        if request.url.path in ["/health", "/metrics"] or request.url.path.startswith("/dashboard"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Security credentials missing or malformed."}
            )

        raw_token = auth_header.split(" ")[1]

        # Enforce SHA-256 token hashing to neutralize proxy timing leaks completely
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        cache_client: aioredis.Redis = request.app.state.cache_layer
        identity_profile = await cache_client.hgetall(f"gateway:identities:{token_hash}")

        if not identity_profile:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Access unauthorized. Invalid credential signature."}
            )

        if identity_profile.get("status") != "active":
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access configuration suspended for this token entity."}
            )

        # Propagate identity downstream the network stack handlers
        request.state.tenant_id = identity_profile.get("tenant_id", "anonymous")
        request.state.token_hash = token_hash

        return await call_next(request)
