# Database Setup and Operations Guide

This guide provides operational workflows for initializing, seeding, and maintaining the PostgreSQL database (Supabase) used by the multi-agent orchestrator system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Key Database Files](#key-database-files)
3. [Initial Setup Workflow](#initial-setup-workflow)
4. [Detailed Operations](#detailed-operations)
   - [1. Schema Initialization](#1-schema-initialization)
   - [2. Enabling Row-Level Security (RLS)](#2-enabling-row-level-security-rls)
   - [3. Creating the Default Test Owner](#3-creating-the-default-test-owner)
   - [4. Generating Seed Data](#4-generating-seed-data)
   - [5. Loading Seed Data](#5-loading-seed-data)
   - [6. Generating Policy Documents](#6-generating-policy-documents)
   - [7. Ingesting Policy Documents](#7-ingesting-policy-documents)
   - [8. Generating Business Embeddings](#8-generating-business-embeddings)
5. [Verification Commands](#verification-commands)
6. [Recommended Fresh Setup Sequence](#recommended-fresh-setup-sequence)
7. [Common Gotchas](#common-gotchas)

---

## Prerequisites

### 1. Environment Variables

Create a `.env` file at the project root with the following required variables:

```bash
# Database connection (Supabase PostgreSQL)
SUPABASE_DB_URL=postgresql://postgres.[project-ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres

# OpenAI API (required for embeddings)
OPENAI_API_KEY=your-openai-api-key-here
EMBEDDING_MODEL=text-embedding-3-small
```

### 2. Python Environment

Ensure you have `uv` and Python 3.11+ installed:

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync
```

### 3. Database Requirements

- A Supabase PostgreSQL instance (or compatible PostgreSQL 13+)
- The `vector` extension (pgvector) must be available
- Database user must have `CREATE EXTENSION` privileges

---

## Key Database Files

All database-related scripts are located in `backend/db/`:

| File | Purpose |
|------|---------|
| **`init_db.py`** | Creates all tables, enables pgvector extension, applies schema rollouts |
| **`ENABLE_RLS.sql`** | SQL script that enables Row-Level Security (RLS) on all tables with `owner_id` |
| **`generate_seed_data.py`** | Generates realistic CSV seed data for business entities |
| **`load_seed_data.py`** | Loads CSV seed data into database tables |
| **`generate_policies.py`** | Generates business policy PDF documents |
| **`ingest_policies.py`** | Converts policy PDFs to Markdown, chunks them, embeds them, and stores in `policy_chunks` |
| **`ingest_business_data.py`** | Generates embeddings for business entity descriptions (products, contracts, agreements) |
| **`models.py`** | SQLAlchemy ORM models defining all database tables |
| **`engine.py`** | Database engine and session factory (lazy initialization) |

---

## Initial Setup Workflow

For a **brand new** database, follow this sequence:

```bash
# 1. Initialize schema
uv run python backend/db/init_db.py

# 2. Enable RLS (run SQL script via psql or Supabase SQL Editor)
psql $SUPABASE_DB_URL -f backend/db/ENABLE_RLS.sql

# 3. Create default test owner
uv run python insert_user.py

# 4. Generate seed data
uv run python backend/db/generate_seed_data.py

# 5. Load seed data
uv run python backend/db/load_seed_data.py

# 6. Generate policies
uv run python backend/db/generate_policies.py

# 7. Ingest policies (embed and chunk)
uv run python backend/db/ingest_policies.py

# 8. Embed business data
uv run python backend/db/ingest_business_data.py
```

---

## Detailed Operations

### 1. Schema Initialization

**Script:** `backend/db/init_db.py`

**What it does:**
- Enables the `pgvector` extension
- Creates all tables defined in `backend/db/models.py` using SQLAlchemy's `Base.metadata.create_all()`
- Applies conversation memory schema rollout (adds `conversation_threads`, `conversation_sender_memories`, etc.)
- Adds `held_reply_id` column and foreign key to `pending_approvals` table

**Usage:**

```bash
uv run python backend/db/init_db.py
```

**Output:**
```
Creating tables...
Done.
```

**When to run:**
- First time setting up the database
- After adding new ORM models to `models.py`
- To repair missing tables (idempotent)

**Notes:**
- This script is **idempotent** — safe to run multiple times
- Does **not** drop existing tables or data
- Uses `CREATE TABLE IF NOT EXISTS` and conditional column additions

---

### 2. Enabling Row-Level Security (RLS)

**Script:** `backend/db/ENABLE_RLS.sql`

**What it does:**
- Enables Row-Level Security (RLS) on all tables that have an `owner_id` column
- Creates policies that restrict all operations (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) to rows where `owner_id = auth.uid()`
- Special-cases the `profiles` table to use `id = auth.uid()` instead of `owner_id`

**Usage:**

Via `psql`:

```bash
psql $SUPABASE_DB_URL -f backend/db/ENABLE_RLS.sql
```

Or via Supabase SQL Editor:
1. Open your Supabase Dashboard → SQL Editor
2. Copy the contents of `backend/db/ENABLE_RLS.sql`
3. Paste and execute

**When to run:**
- **After** running `init_db.py` to create tables
- When deploying to production to enforce multi-tenant isolation
- Only needed **once** per database (policies persist)

**Notes:**
- RLS policies are **not required** for local development
- The default test owner (`4c116430-f683-4a8a-91f7-546fa8bc5d76`) must exist in `auth.users` for RLS policies to allow data access
- Running this script multiple times is safe (checks for existing policies)

---

### 3. Creating the Default Test Owner

**Script:** `insert_user.py` (located at project root)

**What it does:**
- Creates a test user in `auth.users` with:
  - Email: `test@gmail.com`
  - Password: `Abcd@1234`
  - UUID: `4c116430-f683-4a8a-91f7-546fa8bc5d76`
- Creates a corresponding profile in `public.profiles`
- Uses `ON CONFLICT DO UPDATE/NOTHING` to be idempotent

**Usage:**

```bash
uv run python insert_user.py
```

**Output:**
```
Successfully inserted auth.users row!
Successfully inserted profile row!
```

**When to run:**
- **Before** loading seed data (seed data references this owner ID)
- When setting up a new database instance
- To reset the test user password

**Notes:**
- This owner ID is **hardcoded** in all seed generation scripts
- The password is hashed using `bcrypt`
- Safe to run multiple times (updates password on conflict)

---

### 4. Generating Seed Data

**Script:** `backend/db/generate_seed_data.py`

**What it does:**
- Generates realistic business data and writes it to CSV files in `backend/data/seed/`:
  - `products.csv` (10 products: electronics, accessories)
  - `customers.csv` (5 customers with companies and preferences)
  - `suppliers.csv` (3 suppliers in different categories)
  - `partners.csv` (2 partners: media, platform)
  - `orders.csv` (20 orders linking customers and products)
  - `supply_contracts.csv` (supplier-product relationships with pricing) → loads into `supplier_products` table
  - `partner_agreements.csv` (revenue-share agreements)
  - `partner_products.csv` (partner-product relationships) → loads into `partner_product_relations` table

**Usage:**

```bash
uv run python backend/db/generate_seed_data.py
```

**Output:**
```
Generated 10 rows → products.csv
Generated 5 rows → customers.csv
Generated 3 rows → suppliers.csv
Generated 2 rows → partners.csv
Generated 20 rows → orders.csv
Generated 12 rows → supply_contracts.csv
Generated 2 rows → partner_agreements.csv
Generated 6 rows → partner_products.csv
Seed data generation complete.
```

**When to run:**
- Before loading seed data (`load_seed_data.py`)
- When you want to regenerate sample data with different random values
- After modifying the seed data structure

**Notes:**
- All generated entities belong to owner ID `4c116430-f683-4a8a-91f7-546fa8bc5d76`
- UUIDs are randomly generated each time the script runs
- Safe to run multiple times (overwrites existing CSV files)

---

### 5. Loading Seed Data

**Script:** `backend/db/load_seed_data.py`

**What it does:**
- Reads CSV files from `backend/data/seed/`
- Loads data into database tables in foreign-key-safe order:
  1. `products`
  2. `customers`
  3. `suppliers`
  4. `partners`
  5. `orders` (references customers, products)
  6. `supplier_products` (references suppliers, products)
  7. `partner_agreements` (references partners)
  8. `partner_product_relations` (references partners, products, agreements)
- **Idempotent:** Skips any table that already contains data

**Usage:**

```bash
# Standard load (no embeddings)
uv run python backend/db/load_seed_data.py

# Load with embeddings (requires OpenAI API key)
uv run python backend/db/load_seed_data.py --with-embeddings
```

**Output:**
```
  loaded 10 rows → products
  loaded 5 rows → customers
  loaded 3 rows → suppliers
  loaded 2 rows → partners
  loaded 20 rows → orders
  loaded 12 rows → supplier_products
  loaded 2 rows → partner_agreements
  loaded 6 rows → partner_product_relations
Seed data loaded.
Done.
```

**When to run:**
- After generating seed data (`generate_seed_data.py`)
- On fresh database setup
- When tables are empty and you want sample data

**Notes:**
- **Idempotent:** If a table already has rows, it is skipped
- Use `--with-embeddings` to generate embeddings immediately after loading (saves a separate step)
- Embedding generation is concurrent across tables for performance

---

### 6. Generating Policy Documents

**Script:** `backend/db/generate_policies.py`

**What it does:**
- Generates business policy PDF documents in `backend/data/policies/`:
  - `pricing_policy.pdf`
  - `returns_policy.pdf`
  - `data_privacy_policy.pdf`
  - `supplier_terms.pdf`
  - `partner_agreement_policy.pdf`
  - `owner_benefit_rules.pdf`
- Generates `policies_metadata.json` with category and constraint metadata
- Uses `reportlab` to create structured PDFs with headings and body text

**Usage:**

```bash
uv run python backend/db/generate_policies.py
```

**Output:**
```
Generated pricing_policy.pdf
Generated returns_policy.pdf
Generated data_privacy_policy.pdf
Generated supplier_terms.pdf
Generated partner_agreement_policy.pdf
Generated owner_benefit_rules.pdf
Generated policies_metadata.json
Policy generation complete.
```

**When to run:**
- Before ingesting policies (`ingest_policies.py`)
- When policy content has been updated in the script
- To regenerate all policy PDFs from scratch

**Notes:**
- Policy content is **hardcoded** in `POLICY_CONTENT` dictionary
- Metadata comes from `backend/data/policy_metadata.py`
- Stale PDFs (not in `POLICY_SPECS`) are automatically deleted

---

### 7. Ingesting Policy Documents

**Script:** `backend/db/ingest_policies.py`

**What it does:**
- Converts each policy PDF to Markdown using `docling` (structure-aware extraction)
- Splits Markdown into chunks using `MarkdownTextSplitter` (respects heading boundaries)
- Embeds each chunk using OpenAI embeddings
- Stores chunks in the `policy_chunks` table with:
  - `source_file`, `page_number`, `chunk_index`
  - `chunk_text`, `subheading`, `category`
  - `hard_constraint` (from metadata)
  - `embedding` (pgvector)

**Usage:**

```bash
# Standard ingest (skips existing chunks)
uv run python backend/db/ingest_policies.py

# Force re-ingest (deletes and recreates all chunks)
uv run python backend/db/ingest_policies.py --force
```

**Output:**
```
Loaded metadata overrides for 6 file(s) from policies_metadata.json.
  ingesting pricing_policy.pdf ...
  stored 8 chunks
  ingesting returns_policy.pdf ...
  stored 7 chunks
  ...
Done.
```

**When to run:**
- After generating policy PDFs (`generate_policies.py`)
- When policy content has changed (use `--force`)
- To repair missing or corrupted embeddings

**Notes:**
- **Idempotent by default:** Skips files that already have chunks in the database
- Use `--force` to delete existing chunks and re-ingest everything
- Requires `OPENAI_API_KEY` in `.env`
- Embedding is done in **batched API calls** for efficiency
- Chunk size and overlap are configured in `backend/config.py` (`POLICY_CHUNK_SIZE`, `POLICY_CHUNK_OVERLAP`)

---

### 8. Generating Business Embeddings

**Script:** `backend/db/ingest_business_data.py`

**What it does:**
- Generates embeddings for description columns in business tables:
  - **`products.description_embedding`**: Embeds `"{name}: {description}"`
  - **`supplier_products.notes_embedding`**: Embeds `notes`
  - **`partner_agreements.description_embedding`**: Embeds `"{description} {notes}"`
- Skips rows with NULL text fields or existing embeddings (unless `--force`)
- Uses batched API calls for efficiency

**Usage:**

```bash
# Embed all tables
uv run python backend/db/ingest_business_data.py

# Force re-embed all rows
uv run python backend/db/ingest_business_data.py --force

# Embed only one table
uv run python backend/db/ingest_business_data.py --table products
```

**Output:**
```
  embedding products ...
  embedded 10 rows
  embedding supplier_products ...
  embedded 12 rows
  embedding partner_agreements ...
  embedded 2 rows
Done.
```

**When to run:**
- After loading seed data (`load_seed_data.py`)
- When business data descriptions have been updated
- To repair missing embeddings

**Notes:**
- **Idempotent:** Only embeds rows that don't already have embeddings (unless `--force`)
- Requires `OPENAI_API_KEY` in `.env`
- Embedding model is configured via `EMBEDDING_MODEL` in `.env`
- `--table` option allows selective re-embedding of a single table

---

## Verification Commands

Use these SQL queries to verify database state.

### Check if tables exist

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### Check row counts

```sql
SELECT
  'products' AS table_name, COUNT(*) AS row_count FROM products
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
UNION ALL SELECT 'partners', COUNT(*) FROM partners
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'supplier_products', COUNT(*) FROM supplier_products
UNION ALL SELECT 'partner_agreements', COUNT(*) FROM partner_agreements
UNION ALL SELECT 'partner_product_relations', COUNT(*) FROM partner_product_relations
UNION ALL SELECT 'policy_chunks', COUNT(*) FROM policy_chunks;
```

### Check if vector extension is enabled

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Check RLS status

```sql
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

### Check if test owner exists

```sql
SELECT id, email FROM auth.users WHERE id = '4c116430-f683-4a8a-91f7-546fa8bc5d76';
```

### Check embedding coverage

```sql
-- Products with embeddings
SELECT
  COUNT(*) FILTER (WHERE description_embedding IS NOT NULL) AS embedded,
  COUNT(*) FILTER (WHERE description_embedding IS NULL) AS missing
FROM products;

-- Supplier products with embeddings
SELECT
  COUNT(*) FILTER (WHERE notes_embedding IS NOT NULL) AS embedded,
  COUNT(*) FILTER (WHERE notes_embedding IS NULL) AS missing
FROM supplier_products;

-- Partner agreements with embeddings
SELECT
  COUNT(*) FILTER (WHERE description_embedding IS NOT NULL) AS embedded,
  COUNT(*) FILTER (WHERE description_embedding IS NULL) AS missing
FROM partner_agreements;
```

### Check policy chunks

```sql
SELECT
  source_file,
  COUNT(*) AS chunk_count
FROM policy_chunks
GROUP BY source_file
ORDER BY source_file;
```

---

## Recommended Fresh Setup Sequence

For a **completely fresh** database (no tables, no data):

```bash
# 1. Ensure environment variables are set
source .env  # or verify SUPABASE_DB_URL and OPENAI_API_KEY are set

# 2. Initialize schema
uv run python backend/db/init_db.py

# 3. Enable RLS (optional for dev, required for production)
psql $SUPABASE_DB_URL -f backend/db/ENABLE_RLS.sql

# 4. Create test owner
uv run python insert_user.py

# 5. Generate and load seed data
uv run python backend/db/generate_seed_data.py
uv run python backend/db/load_seed_data.py

# 6. Generate and ingest policies
uv run python backend/db/generate_policies.py
uv run python backend/db/ingest_policies.py

# 7. Embed business data
uv run python backend/db/ingest_business_data.py

# 8. Verify setup
psql $SUPABASE_DB_URL -c "SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'policy_chunks', COUNT(*) FROM policy_chunks;"
```

**Expected output:**
- Products: 10 rows
- Customers: 5 rows
- Suppliers: 3 rows
- Partners: 2 rows
- Orders: 20 rows
- Policy chunks: ~40-50 chunks (varies by chunking config)
- All products, contracts, and agreements should have embeddings

---

## Common Gotchas

### 1. **Missing `SUPABASE_DB_URL`**

**Symptom:** `RuntimeError: SUPABASE_DB_URL is not configured.`

**Fix:** Ensure `.env` contains a valid Supabase connection string:

```bash
SUPABASE_DB_URL=postgresql://postgres.[project-ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres
```

### 2. **Missing `OPENAI_API_KEY`**

**Symptom:** Embedding scripts fail with authentication errors.

**Fix:** Add `OPENAI_API_KEY` to `.env`:

```bash
OPENAI_API_KEY=sk-...
```

### 3. **`auth.users` table does not exist**

**Symptom:** `insert_user.py` fails with `relation "auth.users" does not exist`.

**Fix:** The `auth` schema is managed by Supabase. Ensure you're using a **Supabase PostgreSQL instance**, not a plain PostgreSQL database. If using plain PostgreSQL, you'll need to manually create the `auth.users` table or modify the script to use `public.users`.

### 4. **RLS prevents data access**

**Symptom:** Queries return empty results even though data exists.

**Fix:**
- Ensure the test owner (`4c116430-f683-4a8a-91f7-546fa8bc5d76`) exists in `auth.users`
- Set the current user context before querying:
  ```sql
  SET LOCAL auth.uid = '4c116430-f683-4a8a-91f7-546fa8bc5d76';
  ```
- Or disable RLS temporarily for testing:
  ```sql
  ALTER TABLE products DISABLE ROW LEVEL SECURITY;
  ```

### 5. **Seed data already loaded**

**Symptom:** `load_seed_data.py` skips all tables with message "already has data".

**Fix:** This is **intentional** (idempotent behavior). If you want to reload:
- Either delete existing rows:
  ```sql
  TRUNCATE products, customers, suppliers, partners, orders, supplier_products, partner_agreements, partner_product_relations CASCADE;
  ```
- Or modify the script to force reload.

### 6. **Policy PDFs not found**

**Symptom:** `ingest_policies.py` says "No PDFs found".

**Fix:** Run `generate_policies.py` first:

```bash
uv run python backend/db/generate_policies.py
```

### 7. **Foreign key constraint violations**

**Symptom:** `load_seed_data.py` fails with foreign key errors.

**Fix:**
- Ensure the test owner exists (`insert_user.py` was run)
- Ensure CSV files are present and correctly formatted
- The load order in the script respects foreign key dependencies — do not modify the order

### 8. **Embedding failures due to rate limits**

**Symptom:** Embedding scripts fail partway through with rate limit errors.

**Fix:**
- Use a paid OpenAI API key with higher rate limits
- Reduce `_BATCH_SIZE` in `ingest_business_data.py` and `ingest_policies.py`
- Add retry logic or delay between batches

### 9. **Stale embeddings after data changes**

**Symptom:** Search results don't reflect updated product/policy content.

**Fix:** Re-run embedding scripts with `--force`:

```bash
uv run python backend/db/ingest_policies.py --force
uv run python backend/db/ingest_business_data.py --force
```

### 10. **Docker container auto-runs scripts but data seems missing**

**Symptom:** Backend container logs show "seed data loaded" but queries return empty.

**Fix:**
- Check container logs: `docker compose logs backend`
- Verify RLS is not blocking access (see Gotcha #4)
- Verify the database volume persists across restarts
- Check that `init_db.py`, `generate_seed_data.py`, `load_seed_data.py`, `generate_policies.py`, and `ingest_business_data.py` all completed successfully in logs

---

## Quick Reference Commands

| Task | Command |
|------|---------|
| **Initialize schema** | `uv run python backend/db/init_db.py` |
| **Enable RLS** | `psql $SUPABASE_DB_URL -f backend/db/ENABLE_RLS.sql` |
| **Create test owner** | `uv run python insert_user.py` |
| **Generate seed CSVs** | `uv run python backend/db/generate_seed_data.py` |
| **Load seed data** | `uv run python backend/db/load_seed_data.py` |
| **Generate policy PDFs** | `uv run python backend/db/generate_policies.py` |
| **Ingest policies** | `uv run python backend/db/ingest_policies.py` |
| **Embed business data** | `uv run python backend/db/ingest_business_data.py` |
| **Force re-embed policies** | `uv run python backend/db/ingest_policies.py --force` |
| **Force re-embed business data** | `uv run python backend/db/ingest_business_data.py --force` |
| **Embed single table** | `uv run python backend/db/ingest_business_data.py --table products` |

---

## Docker Automation

When using Docker Compose (recommended), the backend container **automatically runs** the following on startup:

1. `backend/db/init_db.py`
2. `backend/db/generate_seed_data.py`
3. `backend/db/load_seed_data.py`
4. `backend/db/generate_policies.py`
5. `backend/db/ingest_business_data.py`

See `docker-compose.yml` and `docker-entrypoint.sh` (or equivalent) for details.

**To manually re-run inside the container:**

```bash
docker compose exec backend uv run python backend/db/generate_seed_data.py
docker compose exec backend uv run python backend/db/load_seed_data.py
docker compose exec backend uv run python backend/db/generate_policies.py
docker compose exec backend uv run python backend/db/ingest_business_data.py
```

---

## Further Reading

- **SQLAlchemy ORM Models:** `backend/db/models.py`
- **Database Engine Configuration:** `backend/db/engine.py`
- **Policy Metadata Definitions:** `backend/data/policy_metadata.py`
- **Application Config (chunking, embeddings):** `backend/config.py`

---

**Last Updated:** 2026-04-03
