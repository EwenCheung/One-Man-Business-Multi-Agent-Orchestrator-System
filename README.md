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

Required environment values for the current setup:
- `SUPABASE_DB_URL` — pooled Postgres connection string
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `BACKEND_PUBLIC_URL` — public HTTPS backend URL used for Telegram webhook registration

## Start The Project

### Option 1: Docker (Recommended)
```bash
docker compose up -d --build
```

Services:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- PostgreSQL: `localhost:5432`

Docker startup does **not** automatically reset or reseed the database.

Useful commands:
```bash
# Logs
docker compose logs -f backend frontend db

# Reset and reseed Supabase manually
docker compose exec backend uv run python backend/db/reset_and_seed_supabase.py

# Stop
docker compose down
```

### Option 2: Manual Run

Backend:
```bash
uv sync
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

The frontend now reads environment variables from the shared repo-root `.env` via its npm scripts. Do not keep a separate `frontend/.env.local` for normal development.

## Reset and Load Seed Data

To fully wipe business data and load the current 2-owner seed set:

```bash
uv run python backend/db/reset_and_seed_supabase.py
```

This creates:

- `owner1@gmail.com`, `customer1@gmail.com`, `supplier1@gmail.com`, `partner1@gmail.com`, `investor1@gmail.com`
- `owner2@gmail.com`, `customer2@gmail.com`, `supplier2@gmail.com`, `partner2@gmail.com`, `investor2@gmail.com`

Default password for seeded auth users:

```text
Abcd@1234
```

## Telegram Owner Setup

Telegram is configured from the **Owner Dashboard → Profile → Telegram Integration** section.

You provide there:

- **Bot Token**
- **Webhook Secret**

The app uses `BACKEND_PUBLIC_URL` from env to construct the actual webhook URL automatically:

```text
${BACKEND_PUBLIC_URL}/api/v1/telegram/webhook
```

When you save the owner profile and both Telegram fields are present, the app automatically calls Telegram `setWebhook(...)` again.

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
