import asyncio
import httpx


async def verify_gateway_deployment():
    print("Initiating verification smoke test harness...")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get("http://localhost:8000/health")
            print(f"Deployment status signature: {res.status_code}")
            print(f"Server metadata envelope content: {res.json()}")
        except Exception as e:
            print(f"Verification failure sequence initialized. Reason: {e}")


if __name__ == "__main__":
    asyncio.run(verify_gateway_deployment())
