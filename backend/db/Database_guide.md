# Database Guide

## Resetting the Database to Seed Data

If you need to completely reset your database back to the initial seed data state, follow these steps. **Warning: This will destroy all current data in the database.**

From the root of the project, run the following commands manually:

```bash
uv run python backend/db/init_db.py
uv run python backend/db/generate_seed_data.py
uv run python backend/db/load_seed_data.py
uv run python backend/db/generate_policies.py
uv run python backend/db/ingest_business_data.py
```

This will:
1. Re-initialize the database schema (dropping and recreating tables).
2. Generate fresh mock seed data CSVs.
3. Load the seed data CSVs into the database.
4. Generate the policy PDFs.
5. Ingest the business data and embed vectors.
