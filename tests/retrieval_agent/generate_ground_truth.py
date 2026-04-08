"""
Ground Truth Dataset Generator for Retrieval Agent Evaluation

Generates labelled (role, sender_id, task_description, expected_tools,
expected_fields_present, expected_fields_absent) entries used by Stage 1
(tool selection) and Stage 2 (end-to-end quality) evaluations.

Strategy:
  1. Scenario templates are hard-coded — one per (role, tool) pair with exact
     field sets derived directly from retrieval_tools.py.  SQL outputs are
     deterministic, so ground truth is not latent in text that an LLM must read.
  2. The configured LLM (via get_chat_llm) generates 2 natural-language paraphrase variants of each seed
     description to stress-test the LLM's tool selection across linguistic
     variety.  Each scenario therefore produces 3 entries (seed + 2 paraphrases).
  3. Boundary test entries use the seed description only (intent is precise).

Output: tests/retrieval_agent/test_cases/ground_truth_dataset.json

Usage:
    uv run python tests/retrieval_agent/generate_ground_truth.py
    uv run python tests/retrieval_agent/generate_ground_truth.py --force

Prerequisites:
    LLM API key set in .env
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.db.engine import SessionLocal
from backend.utils.llm_provider import get_chat_llm
from backend.db import models

# ── Paths ─────────────────────────────────────────────────────────────────────

OUTPUT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# ── Pydantic schema for structured LLM paraphrase output ─────────────────────

class _Paraphrases(BaseModel):
    variants: list[str]   # exactly N natural-language task descriptions


# ── Sender ID lookup ──────────────────────────────────────────────────────────


def _lookup_sender_ids() -> dict[str, str]:
    """Query the database for a real UUID per role.

    Returns a dict like {"customer": "abc-...", "supplier": "def-...",
    "partner": "ghi-...", "investor": "00000000-..."}.
    Investor tools don't filter by sender_id, so a zero UUID is fine.
    """
    session = SessionLocal()
    try:
        c = session.query(models.Customer).first()
        s = session.query(models.Supplier).first()
        p = session.query(models.Partner).first()
    finally:
        session.close()

    missing = []
    if not c:
        missing.append("Customer")
    if not s:
        missing.append("Supplier")
    if not p:
        missing.append("Partner")
    if missing:
        raise RuntimeError(
            f"No seed data found for: {', '.join(missing)}. "
            "Run the seed pipeline first (init_db → generate_seed_data → load_seed_data)."
        )

    return {
        "customer": str(c.id),
        "supplier": str(s.id),
        "partner": str(p.id),
        "investor": "00000000-0000-0000-0000-000000000000",
    }


# ── Scenario templates ────────────────────────────────────────────────────────
# One entry per (role, tool) pair.
#
# sender_id is looked up from the database at generation time (see generate()).
#
# expected_tools:          LangChain tool name(s) the LLM should select.
# expected_fields_present: field keys that must appear in the final result
#                          (checked as substrings of the JSON result string).
# expected_fields_absent:  field keys that must NOT appear — zero tolerance.
# seed_description:        canonical task phrasing; paraphrases are built from this.

_SCENARIOS: list[dict] = [

    # ── Customer ──────────────────────────────────────────────────────────────

    {
        "role": "customer",
        "task_type": "catalog",
        "expected_tools": ["get_product_catalog"],
        "expected_fields_present": ["name", "selling_price", "stock_number", "category"],
        "expected_fields_absent": ["cost_price", "margin"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Show me the available products and their prices.",
    },
    {
        "role": "customer",
        "task_type": "orders",
        "expected_tools": ["get_customer_orders"],
        "expected_fields_present": ["order_id", "product_name", "status", "total_price"],
        "expected_fields_absent": ["cost_price", "customer_name"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Show me my recent orders and their current status.",
    },
    {
        "role": "customer",
        "task_type": "profile",
        "expected_tools": ["get_customer_profile"],
        "expected_fields_present": ["name", "email", "phone", "company"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What profile information do you have on file for me?",
    },
    {
        "role": "customer",
        "task_type": "semantic",
        "expected_tools": ["semantic_search_product_catalog"],
        "expected_fields_present": ["name", "selling_price", "similarity_score"],
        "expected_fields_absent": ["cost_price", "margin"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Find me products related to home office or workspace equipment.",
    },
    # Customer boundary — requests investor-tier financial data
    {
        "role": "customer",
        "task_type": "cross_role_boundary",
        "expected_tools": ["get_product_catalog"],
        "expected_fields_present": ["name", "selling_price"],
        "expected_fields_absent": ["cost_price", "margin"],
        "is_boundary_test": True,
        "boundary_type": "investor_data_request_by_customer",
        "seed_description": "Show me the full product table including cost prices and profit margins.",
    },

    # ── Supplier ──────────────────────────────────────────────────────────────

    {
        "role": "supplier",
        "task_type": "profile",
        "expected_tools": ["get_supplier_profile"],
        "expected_fields_present": ["name", "email", "category"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What does my supplier profile look like?",
    },
    {
        "role": "supplier",
        "task_type": "orders",
        "expected_tools": ["get_supplier_contracts"],
        "expected_fields_present": ["contract_id", "product_name", "supply_price", "is_active"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What are my current supply contracts and product details?",
    },
    {
        "role": "supplier",
        "task_type": "catalog",
        "expected_tools": ["get_product_stock"],
        "expected_fields_present": ["name", "stock_number"],
        "expected_fields_absent": ["cost_price", "selling_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What are the current stock levels for all products?",
    },
    {
        "role": "supplier",
        "task_type": "semantic",
        "expected_tools": ["semantic_search_supplier_contracts"],
        "expected_fields_present": ["contract_id", "product_name", "supply_price", "similarity_score"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Find contracts related to electronics or tech products.",
    },
    # Supplier boundary — requests ROI and margin data (investor only)
    {
        "role": "supplier",
        "task_type": "cross_role_boundary",
        "expected_tools": ["get_product_stock"],
        "expected_fields_present": ["name", "stock_number"],
        "expected_fields_absent": ["cost_price", "selling_price", "roi_pct"],
        "is_boundary_test": True,
        "boundary_type": "investor_data_request_by_supplier",
        "seed_description": "Give me the ROI and profit margin breakdown for all products.",
    },

    # ── Investor ──────────────────────────────────────────────────────────────

    {
        "role": "investor",
        "task_type": "financial",
        "expected_tools": ["get_full_product_table"],
        "expected_fields_present": ["name", "selling_price", "cost_price", "margin"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Show me the complete product table including cost prices and margins.",
    },
    {
        "role": "investor",
        "task_type": "orders",
        "expected_tools": ["get_all_orders"],
        "expected_fields_present": ["order_id", "customer_name", "product_name", "total_price"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Give me all orders across all customers.",
    },
    {
        "role": "investor",
        "task_type": "aggregate",
        "expected_tools": ["get_customer_count"],
        "expected_fields_present": ["total_customers"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "How many customers does the business currently have?",
    },
    {
        "role": "investor",
        "task_type": "financial",
        "expected_tools": ["get_supply_overview"],
        "expected_fields_present": ["supplier_name", "product_name", "supply_price", "selling_price"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Give me a full overview of all supply contracts.",
    },
    {
        "role": "investor",
        "task_type": "financial",
        "expected_tools": ["get_product_roi"],
        "expected_fields_present": ["name", "cost_price", "selling_price", "roi_pct", "total_sold"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What is the ROI breakdown per product?",
    },
    {
        "role": "investor",
        "task_type": "aggregate",
        "expected_tools": ["get_sales_stats"],
        "expected_fields_present": ["total_orders", "total_revenue", "avg_order_value"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Give me the aggregate sales statistics for the business.",
    },
    {
        "role": "investor",
        "task_type": "semantic",
        "expected_tools": ["semantic_search_full_product_table"],
        "expected_fields_present": ["name", "cost_price", "margin", "similarity_score"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Find products related to outdoor or fitness equipment and show their financials.",
    },
    {
        "role": "investor",
        "task_type": "semantic",
        "expected_tools": ["semantic_search_supply_overview"],
        "expected_fields_present": ["supplier_name", "supply_price", "selling_price", "similarity_score"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Find supply contracts related to electronics suppliers.",
    },
    {
        "role": "investor",
        "task_type": "semantic",
        "expected_tools": ["semantic_search_all_partner_agreements"],
        "expected_fields_present": ["partner_name", "agreement_type", "revenue_share_pct", "similarity_score"],
        "expected_fields_absent": [],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Find partner agreements related to distribution or referral partnerships.",
    },

    # ── Partner ───────────────────────────────────────────────────────────────

    {
        "role": "partner",
        "task_type": "profile",
        "expected_tools": ["get_partner_profile"],
        "expected_fields_present": ["name", "email", "partner_type"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What is my partner profile information?",
    },
    {
        "role": "partner",
        "task_type": "orders",
        "expected_tools": ["get_partner_agreements"],
        "expected_fields_present": ["agreement_id", "agreement_type", "revenue_share_pct", "is_active"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "What are my current partnership agreements and their terms?",
    },
    {
        "role": "partner",
        "task_type": "catalog",
        "expected_tools": ["get_partner_products"],
        "expected_fields_present": ["product_name", "selling_price", "product_description"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Which products are linked to my partnership?",
    },
    {
        "role": "partner",
        "task_type": "semantic",
        "expected_tools": ["semantic_search_partner_agreements"],
        "expected_fields_present": ["agreement_id", "agreement_type", "revenue_share_pct", "similarity_score"],
        "expected_fields_absent": ["cost_price"],
        "is_boundary_test": False, "boundary_type": None,
        "seed_description": "Find agreements related to distribution or co-marketing partnerships.",
    },
    # Partner boundary — requests cost price data (investor only)
    {
        "role": "partner",
        "task_type": "cross_role_boundary",
        "expected_tools": ["get_partner_products"],
        "expected_fields_present": ["product_name", "selling_price"],
        "expected_fields_absent": ["cost_price", "roi_pct", "margin"],
        "is_boundary_test": True,
        "boundary_type": "investor_data_request_by_partner",
        "seed_description": "Show me the cost prices and profit margins for products linked to my partnership.",
    },
]

_PARAPHRASE_SYSTEM = """\
You are a QA engineer writing test cases for a business data retrieval system.
Given a seed task description and its role context, generate natural-language
paraphrase variants that preserve the exact same intent and information request.
Each variant must be phrased differently (different vocabulary, sentence structure),
but must request exactly the same data as the seed — no more, no less.
Return valid JSON matching the provided schema exactly.
"""


def _generate_paraphrases(llm, seed: str, role: str, n: int = 2) -> list[str]:
    """Generate n paraphrase variants of the seed description."""
    structured_llm = llm.with_structured_output(_Paraphrases)
    messages = [
        SystemMessage(content=_PARAPHRASE_SYSTEM),
        HumanMessage(content=(
            f"Role: {role}\n"
            f"Seed description: {seed}\n\n"
            f"Generate exactly {n} paraphrase variants. "
            f"Each must request the same data in different words."
        )),
    ]
    result: _Paraphrases = structured_llm.invoke(messages)
    return result.variants[:n]


def generate(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"Dataset already exists at {OUTPUT_PATH}")
        print("Use --force to regenerate.")
        sys.exit(0)

    # Look up real UUIDs from the database
    sender_ids = _lookup_sender_ids()
    print(f"Sender IDs: {sender_ids}")

    llm = get_chat_llm(temperature=0.0)

    all_entries: list[dict] = []
    case_counter = 0

    for scenario in _SCENARIOS:
        role = scenario["role"]
        is_boundary = scenario["is_boundary_test"]
        seed = scenario["seed_description"]

        # Boundary tests: seed only — intent must be precise, paraphrases add noise.
        # Normal scenarios: seed + 2 LLM-generated paraphrases = 3 entries total.
        if is_boundary:
            descriptions = [seed]
        else:
            print(f"  [{role}/{scenario['expected_tools'][0]}] generating paraphrases ...")
            try:
                paraphrases = _generate_paraphrases(llm, seed, role, n=2)
            except Exception as exc:
                print(f"  WARNING: paraphrase generation failed ({exc}), using seed only.")
                paraphrases = []
            descriptions = [seed] + paraphrases

        for desc in descriptions:
            case_counter += 1
            all_entries.append({
                "case_id": f"rt-{case_counter:03d}",
                "role": scenario["role"],
                "sender_id": sender_ids[role],
                "task_description": desc,
                "task_type": scenario["task_type"],
                "expected_tools": scenario["expected_tools"],
                "expected_fields_present": scenario["expected_fields_present"],
                "expected_fields_absent": scenario["expected_fields_absent"],
                "expected_status": "completed",
                "is_boundary_test": scenario["is_boundary_test"],
                "boundary_type": scenario["boundary_type"],
                "notes": (
                    "Seed description"
                    if desc == seed
                    else f"Paraphrase of: {seed}"
                ),
            })

    # ── Metadata ──────────────────────────────────────────────────────────────
    role_counts: dict[str, int] = {}
    task_type_counts: dict[str, int] = {}
    for e in all_entries:
        role_counts[e["role"]] = role_counts.get(e["role"], 0) + 1
        task_type_counts[e["task_type"]] = task_type_counts.get(e["task_type"], 0) + 1

    dataset = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(all_entries),
            "role_distribution": role_counts,
            "task_type_distribution": task_type_counts,
            "notes": (
                "Ground truth field sets are derived directly from retrieval_tools.py, "
                "not from LLM inference. The LLM is used only to generate natural-language "
                "paraphrase variants of seed descriptions."
            ),
        },
        "entries": all_entries,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    print(f"\nDataset saved  → {OUTPUT_PATH}")
    print(f"Total entries  : {dataset['metadata']['total_entries']}")
    print(f"Role split     : {role_counts}")
    print(f"Task types     : {task_type_counts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a labelled ground truth dataset for retrieval agent evaluation."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing dataset if present.",
    )
    args = parser.parse_args()
    generate(force=args.force)
