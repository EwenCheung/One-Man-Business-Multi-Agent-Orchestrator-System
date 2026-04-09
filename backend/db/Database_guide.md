# Database Guide

## Resetting the Database to Seed Data

If you need to completely reset your Supabase database back to the current seed data state, use the reset-and-seed script below. **Warning: this deletes existing business data and recreates the seeded owner/stakeholder dataset.**

From the root of the project, run the following commands manually:

```bash
uv run python backend/db/reset_and_seed_supabase.py
```

This will:
1. Ensure seeded owners exist in Supabase Auth (`owner1@gmail.com`, `owner2@gmail.com`).
2. Apply the current schema updates.
3. Wipe business data tables.
4. Recreate owner profiles with empty Telegram bot token and webhook secret.
5. Generate fresh owner-scoped seed CSVs.
6. Load the seed CSVs into Supabase.
7. Recreate login-ready auth users for seeded customers, suppliers, partners, and investors.

The seeded roles are:

- `owner1@gmail.com`, `customer1@gmail.com`, `supplier1@gmail.com`, `partner1@gmail.com`, `investor1@gmail.com`
- `owner2@gmail.com`, `customer2@gmail.com`, `supplier2@gmail.com`, `partner2@gmail.com`, `investor2@gmail.com`

All seeded auth users use password:

```text
Abcd@1234
```
