# One-Man-Business Multi-Agent Orchestrator System

A **role-aware multi-agent auto-reply system** using **LangChain + LangGraph**. Helps business owners draft appropriate replies to different stakeholders (customers, suppliers, investors, partners) with role-specific tone, policy-aware constraints, and risk control.

> 📄 See [AGENTS.md](./AGENTS.md) for the full technical proposal.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Runtime** | Python 3.11+ |
| **Package Manager** | [uv](https://docs.astral.sh/uv/) |
| **Agent Framework** | LangChain + LangGraph |
| **API Framework** | FastAPI |
| **Database** | PostgreSQL + pgvector |

---

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Setup

```bash
# Clone
git clone https://github.com/EwenCheung/One-Man-Business-Multi-Agent-Orchestrator-System.git
cd One-Man-Business-Multi-Agent-Orchestrator-System

# Install dependencies
uv sync

# Install dev dependencies (pytest, ruff)
uv sync --extra dev

# Set up env vars
cp .env.example .env
# Edit .env with your values
```

### Run

```bash
# Start backend
uv run uvicorn backend.main:app --reload

# Run tests
uv run pytest tests/ -v
```

- **Swagger UI**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

---

## Project Structure

```
backend/
├── __init__.py
├── config.py                # Env-driven settings
├── main.py                  # FastAPI app
│
├── models/                  # Pydantic schemas (data in flight)
│   └── __init__.py          # Add your pipeline data models here
│
├── db/                      # SQLAlchemy ORM (data at rest)
│   └── __init__.py          # Add your DB table models here
│
├── agents/                  # LLM-powered agents (LangChain)
│   ├── triage_agent.py          # 7.2  Intent/role classification
│   ├── policy_agent.py          # 7.8  Policy & constraints
│   ├── orchestrator_agent.py    # 7.4  Core planner
│   ├── retriever_agent.py       # 7.5  Internal data retrieval
│   ├── research_agent.py        # 7.6  External research
│   ├── reply_agent.py           # 7.7  Reply generation
│   └── update_agent.py          # 7.10 Memory updates
│
├── nodes/                   # Deterministic nodes (no LLM)
│   ├── receiver.py              # 7.1  Message standardization
│   ├── context_builder.py       # 7.3  Context assembly
│   └── risk.py                  # 7.9  Rule-based risk check
│
├── graph/                   # LangGraph pipeline
│   ├── state.py                 # Shared pipeline state (TypedDict)
│   └── pipeline_graph.py       # StateGraph wiring all nodes/agents
│
├── api/
│   └── router.py            # REST API endpoints
│
tests/
└── test_pipeline_skeleton.py
```

### Where to add your code

| You want to... | Add it in... |
|----------------|-------------|
| Add a new LLM-powered step | `backend/agents/` |
| Add deterministic logic (no LLM) | `backend/nodes/` |
| Define data shapes between steps | `backend/models/` |
| Define database tables | `backend/db/` |
| Change pipeline flow / routing | `backend/graph/pipeline_graph.py` |
| Add/modify the shared state | `backend/graph/state.py` |
| Add API endpoints | `backend/api/router.py` |

---

## Pipeline Flow

```
Incoming Message
  → receiver           (node — standardize)
  → triage_agent       (agent — classify intent/role)
  → context_builder    (node — assemble context)
  → policy_agent       (agent — lookup constraints)
  → orchestrator_agent (agent — plan steps)
  → retriever_agent    (agent — fetch internal data)
  → research_agent     (agent — conditional external research)
  → reply_agent        (agent — generate reply)
  → risk               (node — rule-based risk check)
  → update_agent       (agent — memory updates)
```

---
## Database Schema

```
───────────────────────────────────────────────────────
CORE TABLES
───────────────────────────────────────────────────────

customers
├── id                  PK
├── name
├── email
├── phone
├── address
├── platform            (which platform they came from)
└── created_at

products
├── id                  PK
├── name
├── description
├── selling_price
├── cost_price
├── stock_quantity
├── category
├── link                (url to product page)
├── created_at
└── updated_at

orders
├── id                  PK
├── customer_id         FK → customers
├── product_id          FK → products
├── quantity
├── total_price
├── order_date
├── status              (pending / fulfilled / cancelled)
├── channel
└── created_at

───────────────────────────────────────────────────────
SUPPLIER TABLES
───────────────────────────────────────────────────────

suppliers
├── id                  PK
├── name
├── contact_person
├── email
├── phone
└── created_at

supply_contracts
├── id                  PK
├── supplier_id         FK → suppliers
├── product_id          FK → products
├── supply_price
├── total_order_qty
├── lead_time_days
├── contract_start
├── contract_end
├── is_active
└── notes

───────────────────────────────────────────────────────
PARTNER TABLES
───────────────────────────────────────────────────────

partners
├── id                  PK
├── name
├── contact_person
├── email
├── phone
└── created_at

partner_agreements
├── id                  PK
├── partner_id          FK → partners
├── description
├── agreement_type      (reseller / affiliate / collab)
├── revenue_share_pct
├── start_date
├── end_date
├── is_active
└── notes

partner_products
├── id                  PK
├── partner_id          FK → partners
├── product_id          FK → products
├── agreement_id        FK → partner_agreements
└── created_at

───────────────────────────────────────────────────────
ROLE-BASED ACCESS
───────────────────────────────────────────────────────

CUSTOMER can access:
├── customers       → their own profile only
├── products        → name, description, selling_price, stock_quantity, link, category
└── orders          → their own orders only

SUPPLIER can access:
├── products        → name, description, stock_quantity
├── suppliers       → their own profile only
└── supply_contracts→ their own contracts only

INVESTOR can access:
├── products        → full table including cost_price
├── orders          → full table
├── customers       → aggregate stats (customer count)
├── supply_contracts→ full table
└── metrics         → ROI, daily sales, margins (computed at query time)

PARTNER can access:
├── products            → name, description, selling_price
├── partners            → their own profile only
├── partner_agreements  → their own agreements only
└── partner_products    → their own product links only
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/messages/incoming` | Submit message → run pipeline |
| `GET` | `/api/v1/messages/{thread_id}` | Thread history (stub) |
| `POST` | `/api/v1/messages/{id}/approve` | Approve held reply (stub) |
| `GET` | `/api/v1/dashboard/summary` | Dashboard data (stub) |