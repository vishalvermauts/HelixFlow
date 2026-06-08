FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Explicit factory invocation with uvloop loops and worker allocations
CMD ["uvicorn", "helixflow_gateway.bootstrap:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory", "--loop", "uvloop", "--workers", "4"]
