"""
Internal Retrieval Sub-Agent (PROPOSAL §4.2)

Retrieves internal business data with role-based access control.
Accepts a specific SubTask assigned by the Orchestrator, executes it,
and returns the completed task to be aggregated.

## TODO
- [x] Connect to database (SQL / pgvector) via SQLAlchemy session
- [x] Implement role-based retrieval filtering (sender_role determines what data is visible)
- [x] Separate exact-match retrieval (SQL WHERE) from semantic retrieval (pgvector similarity)
- [ ] Return provenance with each result (source table, record ID, match type)
- [ ] Mark results as: verified_record | inferred_relevance | missing_data
- [ ] Add try/except with structured failure return
- [ ] Add timeout handling for DB queries

Flow:
    1. Read sender_role from the SubTask
    2. Look up allowed tools via role_permissions
    3. Bind only those tools to the LLM
    4. LLM selects and invokes the right tool(s) based on task description
    5. Tool function executes the scoped DB query
    6. Return results as completed task

Input struct:
{
    "task_id": str,          # Unique ID for this task
    "description": str,      # Natural language instruction, e.g. "Get this customer's recent orders"
    "assignee": str,         # "retriever"
    "status": str,           # "pending"
    "result": str,           # Empty string initially
    "sender_role": str,      # "customer" | "supplier" | "investor" | "partner"
    "sender_id": str,        # e.g. "5" — used for row-level scoping
}

Output struct:
{
    "completed_tasks": [
        {
            # ── Original SubTask fields carried through ──
            "task_id": "...",
            "description": "...",
            "assignee": "retriever",
            "sender_role": "customer",
            "sender_id": "5",

            # ── Updated by the agent ──
            "status": "completed" | "failed",
            "result": "..."  # JSON string of query results, or error message
        }
    ]
}
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from backend.db.engine import SessionLocal
from backend.graph.state import SubTask
from backend.tools.role_permissions import get_tools_for_role
from backend.tools import retrieval_tools as rt
from backend.utils.llm_provider import get_chat_llm


# ─── Wrap query functions as LangChain tools ─────────────────
# Each tool closes over a session and handles its own ID scoping.
# The sender_id is injected at call time.

def _build_tools_for_request(role: str, sender_id: str):
    """Build LangChain tool wrappers for the allowed functions, scoped to sender_id."""
    allowed_fns = get_tools_for_role(role)
    allowed_names = {fn.__name__ for fn in allowed_fns}
    tools = []

    # ── Customer tools ───────────────────────────────────────
    if "get_product_catalog" in allowed_names:
        @tool
        def get_product_catalog() -> str:
            """Get the product catalog with name, description, selling price, stock, link, and category."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_product_catalog(session), default=str)
            finally:
                session.close()
        tools.append(get_product_catalog)

    if "get_customer_orders" in allowed_names:
        @tool
        def get_customer_orders() -> str:
            """Get all orders for the current customer, including product name and order status."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_customer_orders(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_customer_orders)

    if "get_customer_profile" in allowed_names:
        @tool
        def get_customer_profile() -> str:
            """Get the current customer's profile information."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_customer_profile(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_customer_profile)

    # ── Supplier tools ───────────────────────────────────────
    if "get_supplier_profile" in allowed_names:
        @tool
        def get_supplier_profile() -> str:
            """Get the current supplier's profile information."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_supplier_profile(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_supplier_profile)

    if "get_supplier_contracts" in allowed_names:
        @tool
        def get_supplier_contracts() -> str:
            """Get all supply contracts for the current supplier, including product details."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_supplier_contracts(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_supplier_contracts)

    if "get_product_stock" in allowed_names:
        @tool
        def get_product_stock() -> str:
            """Get product stock levels — name, description, and current stock quantity only."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_product_stock(session), default=str)
            finally:
                session.close()
        tools.append(get_product_stock)

    # ── Investor tools ───────────────────────────────────────
    if "get_full_product_table" in allowed_names:
        @tool
        def get_full_product_table() -> str:
            """Get the full product table including cost price and margins."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_full_product_table(session), default=str)
            finally:
                session.close()
        tools.append(get_full_product_table)

    if "get_all_orders" in allowed_names:
        @tool
        def get_all_orders() -> str:
            """Get all orders across all customers with product and customer info."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_all_orders(session), default=str)
            finally:
                session.close()
        tools.append(get_all_orders)

    if "get_customer_count" in allowed_names:
        @tool
        def get_customer_count() -> str:
            """Get the total number of customers (aggregate only, no PII)."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_customer_count(session), default=str)
            finally:
                session.close()
        tools.append(get_customer_count)

    if "get_supply_overview" in allowed_names:
        @tool
        def get_supply_overview() -> str:
            """Get full supply contract table for investor analysis."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_supply_overview(session), default=str)
            finally:
                session.close()
        tools.append(get_supply_overview)

    if "get_product_roi" in allowed_names:
        @tool
        def get_product_roi() -> str:
            """Compute per-product ROI: cost, selling price, margin, total units sold, total revenue, and ROI percentage."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_product_roi(session), default=str)
            finally:
                session.close()
        tools.append(get_product_roi)

    if "get_sales_stats" in allowed_names:
        @tool
        def get_sales_stats() -> str:
            """Get aggregate sales statistics: total orders, total revenue, average order value, orders by status."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_sales_stats(session), default=str)
            finally:
                session.close()
        tools.append(get_sales_stats)

    # ── Partner tools ────────────────────────────────────────
    if "get_partner_profile" in allowed_names:
        @tool
        def get_partner_profile() -> str:
            """Get the current partner's profile information."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_partner_profile(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_partner_profile)

    if "get_partner_agreements" in allowed_names:
        @tool
        def get_partner_agreements() -> str:
            """Get all agreements for the current partner."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_partner_agreements(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_partner_agreements)

    if "get_partner_products" in allowed_names:
        @tool
        def get_partner_products() -> str:
            """Get all products linked to the current partner, with product details and agreement info."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_partner_products(session, int(sender_id)), default=str)
            finally:
                session.close()
        tools.append(get_partner_products)

    return tools


def _get_llm():
    """
    Create the LLM instance for the retrieval agent.

    Uses RETRIEVAL_LLM configs if set, otherwise falls back to default LLM config.
    """
    return get_chat_llm(scope="retrieval", temperature=0.0)


def retrieval_agent(task: SubTask) -> dict:
    """
    Execute the specific retrieval instructions.

    1. Reads sender_role and sender_id from the SubTask
    2. Builds role-scoped LangChain tools (sender_id baked in)
    3. Binds tools to the LLM
    4. LLM picks and calls the right tool based on task description
    5. Returns query results as a completed task

    Input state: SubTask
    Returns: dict with 'completed_tasks' list to merge back to main state.
    """
    # 1. Read scope from injected context (Harness rules!)
    ctx = task.get("injected_context", {})
    role = ctx.get("sender_role", "")
    sender_id = ctx.get("sender_id", "")
    description = task.get("description", "")

    completed_task = dict(task)

    # Validate role
    try:
        tools = _build_tools_for_request(role, sender_id)
    except ValueError as e:
        completed_task["status"] = "failed"
        completed_task["result"] = f"Access denied: {e}"
        return {"completed_tasks": [completed_task]}

    if not tools:
        completed_task["status"] = "failed"
        completed_task["result"] = f"No tools available for role: {role}"
        return {"completed_tasks": [completed_task]}

    # Bind tools and invoke
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=(
            "You are an Internal Data Retriever. Your ONLY job is to find and return "
            "factual business data from the company database.\n\n"
            "### Instructions\n"
            "- Execute the retrieval task described in the user message.\n"
            "- Return ONLY data that matches the query. Do NOT fabricate records.\n"
            "- Call the most relevant tool(s) to fulfill the request.\n"
            "- If no tool matches the request, state that the data is not available.\n\n"
            "### Role Access Rules\n"
            "- Customers / Suppliers: NO access to internal margins, cost prices, or supplier source data\n"
            "- Investors: Access subject to NDA tier — full financials and supply overview permitted\n"
            "- Owner: Full access to all data\n\n"
            f"### Sender Role\n{role}"
        )),
        HumanMessage(content=f"### Task\n{description}"),
    ]

    try:
        response = llm_with_tools.invoke(messages)

        # If the LLM made tool calls, execute them
        if response.tool_calls:
            tool_map = {t.name: t for t in tools}
            results = []
            for tool_call in response.tool_calls:
                tool_fn = tool_map.get(tool_call["name"])
                if tool_fn:
                    result = tool_fn.invoke(tool_call["args"])
                    results.append(result)
                else:
                    results.append(f"Tool '{tool_call['name']}' not found in allowed tools.")

            completed_task["status"] = "completed"
            completed_task["result"] = "\n".join(str(r) for r in results)
        else:
            # LLM responded without tool calls — use its text response
            completed_task["status"] = "completed"
            completed_task["result"] = response.content

    except Exception as e:
        completed_task["status"] = "failed"
        completed_task["result"] = f"Retrieval error: {e}"

    return {"completed_tasks": [completed_task]}
