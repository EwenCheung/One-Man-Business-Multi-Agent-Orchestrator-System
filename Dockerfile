# Use the official Python image
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y curl build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Install uv (The blazing fast python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy dependency configs
COPY pyproject.toml uv.lock ./

# Install dependencies (without dev constraints)
RUN uv sync --no-dev

# Copy project files
COPY . .

# Expose FastAPI Port
EXPOSE 8000

# Start backend by initializing DB + seed data, then run ASGI server on 0.0.0.0 for Docker networking
CMD ["sh", "-c", "uv run python backend/db/init_db.py && uv run python backend/db/generate_seed_data.py && uv run python backend/db/load_seed_data.py && uv run python backend/db/generate_policies.py && uv run python backend/db/ingest_policies.py && uv run python backend/db/ingest_business_data.py && uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
