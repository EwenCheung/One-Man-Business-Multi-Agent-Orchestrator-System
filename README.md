# One-Man-Business Multi-Agent Orchestrator System

## Prerequisites
- Git
- Python 3.11+
- Docker Desktop + Docker Compose
- Node.js 24+ (only for manual frontend run)
- `uv` (only for manual backend run): `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Environment Setup
```bash
cp .env.example .env
```

Set at least one provider credentials in `.env`:
- `AI_PROVIDER=auto|openai|gemini`
- `OPENAI_API_KEY` (for OpenAI)
- `GOOGLE_API_KEY` (for Gemini)

Database URL for local host usage:
- `DATABASE_URL=postgresql+psycopg2://business_admin:business_pass@localhost:5432/business_db`

## Start The Project

### Option 1: Docker (Recommended)
```bash
docker compose up -d --build
```

Services:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- PostgreSQL: `localhost:5432`

Backend startup automatically runs:
- `backend/db/init_db.py`
- `backend/db/seed.py --generate --load`

Seed loading is idempotent (existing populated tables are skipped).

Useful commands:
```bash
# Logs
docker compose logs -f backend frontend db

# Re-run seed manually in container
docker compose exec backend uv run python backend/db/seed.py --generate --load

# Stop
docker compose down
```

### Option 2: Manual Run

Backend:
```bash
uv sync
uv run python backend/db/init_db.py
uv run python backend/db/seed.py --generate --load
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## When You Change Code

Rebuild/restart containers:
```bash
docker compose up -d --build
```

Only backend changed:
```bash
docker compose up -d --build backend
```

Only frontend changed:
```bash
docker compose up -d --build frontend
```

Force clean rebuild (no cache):
```bash
docker compose build --no-cache backend frontend
docker compose up -d
```

