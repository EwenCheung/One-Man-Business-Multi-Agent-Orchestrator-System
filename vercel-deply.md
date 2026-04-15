# Vercel Deploy Incident Log & Runbook

> Project: **One-Man-Business-Multi-Agent-Orchestrator-System**  
> Frontend: `omb-frontend`  
> Backend: `omb-backend`

## 1) What happened (repeated issue)

### Symptom seen
- Frontend URL sometimes showed:
  - `Not Found` / `404`
  - or backend JSON at frontend URL:
    ```json
    {"service":"Multi-Agent Orchestrator","status":"ok","health":"/health","docs":"/docs"}
    ```

### Why it happened
- Monorepo root has a backend-focused `vercel.json`:
  - routes `/(.*) -> api/index.py`
  - Python build (`@vercel/python`)
- When frontend deployment context/config was wrong or ambiguous, frontend project picked wrong build/routing behavior.
- In some states, alias/deployment mapping looked “Ready” but served wrong output or 404.

## 2) Errors and important logs captured

### Frontend showed backend output
- `omb-frontend.vercel.app` returned backend health payload.

### Wrong build mode warning in logs (historical)
- Vercel warning observed:
  - `Due to builds existing in your configuration file, project settings will not apply`
  - then Python build path was used.

### Deployment protection behavior
- Some aliases (`...-ewencheungs-projects.vercel.app`) returned `401 Authentication Required` because Vercel Deployment Protection is enabled for those aliases.
- This is separate from app 404 behavior.

## 3) Current known-good state

- Frontend alias: `https://omb-frontend.vercel.app`
- Backend alias: `https://omb-backend.vercel.app`
- Frontend project root directory set to: `frontend/`
- Frontend latest successful production deploy includes Next.js routes (`/`, `/login`, `/dashboard`, etc.).

## 4) Immediate recovery commands (copy/paste)

### A) Verify which app is being served
```bash
curl -i https://omb-frontend.vercel.app/
curl -i https://omb-frontend.vercel.app/login
vercel inspect omb-frontend.vercel.app
```

### B) Force deploy frontend correctly (recommended for this monorepo)
Run from repo root:
```bash
VERCEL_ORG_ID="team_JnK2KldUNZAwXtnaxFiWk8D9" \
VERCEL_PROJECT_ID="prj_bVkBfzRdn9GeEh5tVUpRLhyeHcGA" \
vercel deploy --prod --yes
```

### C) If alias is stale, rebind alias
```bash
vercel alias set <latest-frontend-deployment-url> omb-frontend.vercel.app
```

## 5) Permanent prevention checklist

Use this checklist for all future sessions:

1. **Frontend project setting**
   - Vercel Dashboard → `omb-frontend` → Settings → General
   - Root Directory = `frontend/`

2. **Backend project setting**
   - Keep backend project isolated (`omb-backend`), using backend build config.

2.1 **Machine-check settings (CLI API, no dashboard click needed)**
   ```bash
   vercel api "/v9/projects/prj_bVkBfzRdn9GeEh5tVUpRLhyeHcGA" --raw
   ```
   Confirm these values:
   - `rootDirectory: "frontend/"`
   - `framework: "nextjs"`
   - `gitProviderOptions.createDeployments: "enabled"`

3. **Do not run ambiguous deploy command from wrong context**
   - Avoid plain `vercel deploy` from repo root unless project ID/env vars are explicitly set.

4. **Validate after every production deploy**
   - `GET /` and `GET /login` for frontend
   - `GET /` and `GET /health` for backend

5. **Remember deployment protection behavior**
   - Some project-scoped aliases can return 401 without bypass token; this is expected.

6. **Playwright note**
   - If Playwright opens Vercel Settings and redirects to Google login, that is expected without an authenticated browser session.
   - In that case, use the CLI API check above as a deterministic fallback to verify hardening settings.

## 6) Frontend + backend sanity checks

```bash
# Frontend
curl -s -o /dev/null -w "%{http_code}" https://omb-frontend.vercel.app/
curl -s -o /dev/null -w "%{http_code}" https://omb-frontend.vercel.app/login

# Backend
curl -s -o /dev/null -w "%{http_code}" https://omb-backend.vercel.app/
curl -s -o /dev/null -w "%{http_code}" https://omb-backend.vercel.app/health
```

Expected:
- Frontend `/` and `/login`: `200`
- Backend `/` and `/health`: `200`

## 7) Notes for future AI sessions

- This monorepo has both frontend and backend Vercel projects.
- Root-level `vercel.json` is backend-oriented and can cause frontend mis-deploy if context is wrong.
- If frontend suddenly shows backend JSON or 404, first suspect deployment context/alias mapping before code bugs.
