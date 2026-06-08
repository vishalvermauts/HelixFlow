import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "helixflow_gateway.bootstrap:create_app",
        host="0.0.0.0",
        port=8000,
        factory=True,
        loop="uvloop",
        workers=4,
    )
