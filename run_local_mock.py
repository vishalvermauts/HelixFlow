import hashlib
import uvicorn
from unittest.mock import AsyncMock, MagicMock, patch

# Generate token hash for the local test token
# Token: "local_test_token"
raw_token = "local_test_token"
token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

# In-memory mock storage representing Redis
fake_redis_db = {
    f"gateway:identities:{token_hash}": {
        "status": "active",
        "tenant_id": "local_dev_user"
    },
    "gateway:identities:8d69448a71e6f60e8df64376b4140cb2d0f68eb143111282fd61d628ae91b339": {
        "status": "active",
        "tenant_id": "helix-engine"
    }
}

async def mock_hgetall(key):
    print(f"[Mock Redis] hgetall call for key: {key}")
    return fake_redis_db.get(key, {})

async def mock_ping():
    print("[Mock Redis] ping call")
    return True

async def mock_xadd(name, fields, id="*"):
    print(f"[Mock Telemetry Stream] xadd to {name}: {fields}")
    return "12345-0"

# Set up Redis client and pool mocks
mock_redis = MagicMock()
mock_redis.ping = AsyncMock(side_effect=mock_ping)
mock_redis.hgetall = AsyncMock(side_effect=mock_hgetall)
mock_redis.xadd = AsyncMock(side_effect=mock_xadd)

mock_pool = MagicMock()
mock_pool.disconnect = AsyncMock()

if __name__ == "__main__":
    print("==============================================================")
    print("🚀 STARTING HELIXFLOW GATEWAY IN LOCAL MOCK MODE")
    print("==============================================================")
    print(f"Token to use: {raw_token}")
    print(f"Authorization Header: Authorization: Bearer {raw_token}")
    print("No local Redis instance required. In-memory Mock Redis is active.")
    print("==============================================================")

    # Patch the redis library calls during the FastAPI startup lifecycle
    with patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool), \
         patch("redis.asyncio.Redis", return_value=mock_redis):
        
        # Import the factory and start uvicorn
        from helixflow_gateway.bootstrap import create_app
        app = create_app()
        
        # Run Uvicorn (omitting uvloop to run on Windows)
        uvicorn.run(app, host="127.0.0.1", port=8002)
