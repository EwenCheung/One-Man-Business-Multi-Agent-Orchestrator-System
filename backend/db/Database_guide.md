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
4. Recreate owner profiles with default tone and default `memory_context` / `soul_context` / `rule_context` values.
5. Generate fresh deterministic owner-scoped seed CSVs using the canonical generator: `backend/data/generate_seed_data.py`.
6. Load the seed CSVs into Supabase.
7. Recreate login-ready auth users for seeded customers, suppliers, partners, and investors.

The seeded roles per owner are:

- `owner1@gmail.com`
  - Customers: `customer1A@gmail.com`, `customer1B@gmail.com`, `customer1C@gmail.com`
  - Suppliers: `supplier1A@gmail.com`, `supplier1B@gmail.com`, `supplier1C@gmail.com`
  - Partners: `partner1A@gmail.com`, `partner1B@gmail.com`, `partner1C@gmail.com`
  - Investors: `investor1A@gmail.com`, `investor1B@gmail.com`, `investor1C@gmail.com`
- `owner2@gmail.com`
  - Customers: `customer2A@gmail.com`, `customer2B@gmail.com`, `customer2C@gmail.com`
  - Suppliers: `supplier2A@gmail.com`, `supplier2B@gmail.com`, `supplier2C@gmail.com`
  - Partners: `partner2A@gmail.com`, `partner2B@gmail.com`, `partner2C@gmail.com`
  - Investors: `investor2A@gmail.com`, `investor2B@gmail.com`, `investor2C@gmail.com`

The reset script writes owner bindings to `backend/data/seed/owners.json`. The canonical generator reads this file so all seeded entities use real owner IDs.

All seeded auth users use password:

```text
Abcd@1234
```
