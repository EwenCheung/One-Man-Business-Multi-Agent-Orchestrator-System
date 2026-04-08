"""
Internal Retrieval Sub-Agent (PROPOSAL §4.2)

Retrieves internal business data with role-based access control.
Accepts a specific SubTask assigned by the Orchestrator, executes it,
and returns the completed task to be aggregated.

Flow:
    1. Read sender_role from the SubTask
    2. Look up allowed tools via role_permissions
    3. Bind only those tools to the LLM
    4. LLM selects and invokes the right tool(s) based on task description
    5. Tool function executes the scoped DB query
    6. Return results as completed task
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.models.agent_response import AgentResponse
from backend.graph.state import SubTask
from backend.tools.role_permissions import get_tools_for_role
from backend.tools import retrieval_tools as rt
from backend.utils.llm_provider import get_chat_llm


# ─── Wrap query functions as LangChain tools ─────────────────
# Each tool closes over a session and handles its own ID scoping.
# The sender_id is injected at call time.


def _build_tools_for_request(role: str, sender_id: str, allow_internal_tools: bool = False):
    """Build LangChain tool wrappers for the allowed functions, scoped to sender_id."""
    role = (role or "").lower()
    allow_internal_tools = allow_internal_tools or (role == "owner")
    
    allowed_fns = get_tools_for_role(role)
    allowed_names = {fn.__name__ for fn in allowed_fns}
    if allow_internal_tools:
        allowed_names.add("evaluate_discount_request")
    tools = []

    # ── Customer tools ───────────────────────────────────────
    if "get_product_catalog" in allowed_names:

        @tool
        def get_product_catalog() -> str:
            """Get the product catalog with name, description, selling price, stock, link, and category."""
            session = SessionLocal()
            try:
                if role == "owner" and "get_full_product_table" in allowed_names:
                    return json.dumps(rt.get_full_product_table(session), default=str)
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
                return json.dumps(rt.get_customer_orders(session, sender_id), default=str)
            finally:
                session.close()

        tools.append(get_customer_orders)

    if "get_customer_profile" in allowed_names:

        @tool
        def get_customer_profile() -> str:
            """Get the current customer's profile information."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_customer_profile(session, sender_id), default=str)
            finally:
                session.close()

        tools.append(get_customer_profile)

    if "evaluate_discount_request" in allowed_names:

        @tool
        def evaluate_discount_request(
            product_query: str, quantity: int, requested_discount_pct: float = 0.0
        ) -> str:
            """Internal discount negotiation guidance using stock, selling price, cost, and quantity. Returns internal-only analysis for customer-facing negotiation."""
            session = SessionLocal()
            try:
                return json.dumps(
                    rt.evaluate_discount_request(
                        session, product_query, quantity, requested_discount_pct
                    ),
                    default=str,
                )
            finally:
                session.close()

        tools.append(evaluate_discount_request)

    # ── Supplier tools ───────────────────────────────────────
    if "get_supplier_profile" in allowed_names:

        @tool
        def get_supplier_profile() -> str:
            """Get the current supplier's profile information."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_supplier_profile(session, sender_id), default=str)
            finally:
                session.close()

        tools.append(get_supplier_profile)

    if "get_supplier_contracts" in allowed_names:

        @tool
        def get_supplier_contracts() -> str:
            """Get all supply contracts for the current supplier, including product details."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_supplier_contracts(session, sender_id), default=str)
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
                return json.dumps(rt.get_partner_profile(session, sender_id), default=str)
            finally:
                session.close()

        tools.append(get_partner_profile)

    if "get_partner_agreements" in allowed_names:

        @tool
        def get_partner_agreements() -> str:
            """Get all agreements for the current partner."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_partner_agreements(session, sender_id), default=str)
            finally:
                session.close()

        tools.append(get_partner_agreements)

    if "get_partner_products" in allowed_names:

        @tool
        def get_partner_products() -> str:
            """Get all products linked to the current partner, with product details and agreement info."""
            session = SessionLocal()
            try:
                return json.dumps(rt.get_partner_products(session, sender_id), default=str)
            finally:
                session.close()

        tools.append(get_partner_products)

    # ── Semantic Search tools ────────────────────────────────
    if "semantic_search_product_catalog" in allowed_names:

        @tool
        def semantic_search_product_catalog(query: str, top_k: int = 5) -> str:
            """Find products semantically similar to the query string. Returns catalog fields."""
            session = SessionLocal()
            try:
                if role == "owner" and "semantic_search_full_product_table" in allowed_names:
                    return json.dumps(
                        rt.semantic_search_full_product_table(session, query, top_k), default=str
                    )
                return json.dumps(
                    rt.semantic_search_product_catalog(session, query, top_k), default=str
                )
            finally:
                session.close()

        tools.append(semantic_search_product_catalog)

    if "semantic_search_full_product_table" in allowed_names:

        @tool
        def semantic_search_full_product_table(query: str, top_k: int = 5) -> str:
            """Find products semantically similar to the query string. Returns full product table (investor only)."""
            session = SessionLocal()
            try:
                return json.dumps(
                    rt.semantic_search_full_product_table(session, query, top_k), default=str
                )
            finally:
                session.close()

        tools.append(semantic_search_full_product_table)

    if "semantic_search_supplier_contracts" in allowed_names:

        @tool
        def semantic_search_supplier_contracts(query: str, top_k: int = 5) -> str:
            """Find supply contracts semantically similar to the query string, scoped to current supplier."""
            session = SessionLocal()
            try:
                return json.dumps(
                    rt.semantic_search_supplier_contracts(session, query, sender_id, top_k),
                    default=str,
                )
            finally:
                session.close()

        tools.append(semantic_search_supplier_contracts)

    if "semantic_search_supply_overview" in allowed_names:

        @tool
        def semantic_search_supply_overview(query: str, top_k: int = 5) -> str:
            """Find supply contracts semantically similar to the query string. Returns full overview (investor only)."""
            session = SessionLocal()
            try:
                return json.dumps(
                    rt.semantic_search_supply_overview(session, query, top_k), default=str
                )
            finally:
                session.close()

        tools.append(semantic_search_supply_overview)

    if "semantic_search_all_partner_agreements" in allowed_names:

        @tool
        def semantic_search_all_partner_agreements(query: str, top_k: int = 5) -> str:
            """Find partner agreements semantically similar to the query string across all partners."""
            session = SessionLocal()
            try:
                return json.dumps(
                    rt.semantic_search_all_partner_agreements(session, query, top_k), default=str
                )
            finally:
                session.close()

        tools.append(semantic_search_all_partner_agreements)

    if "semantic_search_partner_agreements" in allowed_names:

        @tool
        def semantic_search_partner_agreements(query: str, top_k: int = 5) -> str:
            """Find partner agreements semantically similar to the query string, scoped to current partner."""
            session = SessionLocal()
            try:
                return json.dumps(
                    rt.semantic_search_partner_agreements(session, query, sender_id, top_k),
                    default=str,
                )
            finally:
                session.close()

        tools.append(semantic_search_partner_agreements)

    return tools


def _build_system_prompt(role: str) -> str:
    """Return the retrieval agent system prompt for the given role."""
    return (
        "You are an Internal Data Retriever. Your ONLY job is to find and return "
        "factual business data from the company database.\n\n"
        "### Instructions\n"
        "- Execute the retrieval task described in the user message.\n"
        "- Return ONLY data that matches the query. Do NOT fabricate records.\n"
        "- Always call the most appropriate available tool and return its results.\n"
        "- Never refuse a task or explain what data you cannot provide — the tools enforce access boundaries automatically.\n"
        "- Always call the most relevant available tool, even if it does not cover all requested fields. Return what the tool provides.\n"
        "- Only return an empty response if absolutely no tool is even partially relevant to the request.\n"
        "- IMPORTANT: Do NOT mention or reference field names like 'cost_price', 'margin', 'roi_pct' when explaining limitations.\n\n"
        "### Role Access Rules\n"
        "- Customers / Suppliers: NO access to internal margins, cost prices, or supplier source data\n"
        "- Investors: Access subject to NDA tier — full financials and supply overview permitted\n"
        "- Owner: Full access to all data\n\n"
        "### Internal Negotiation Rule\n"
        "- Some tools may return INTERNAL-ONLY pricing guidance for the business agent to negotiate safely.\n"
        "- Never expose raw cost price or internal margin to the customer in your final result text.\n"
        f"### Sender Role\n{role}\n"
        "The available tools for this role are the only data you can access. Use them to fulfill the request."
    )


def _get_llm():
    """
    Create the LLM instance for the retrieval agent.

    Uses RETRIEVAL_LLM configs if set, otherwise falls back to default LLM config.
    """
    return get_chat_llm(scope="retrieval", temperature=0.0)


def retrieval_agent(task: SubTask) -> dict[str, list[dict[str, Any]]]:
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
    allow_internal_tools = bool(ctx.get("allow_internal_tools", False))

    completed_task = dict(task)

    # Validate role
    try:
        tools = _build_tools_for_request(role, sender_id, allow_internal_tools)
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
        
        SystemMessage(content=_build_system_prompt(role)),

        HumanMessage(content=f"### Task\n{description}"),
    ]

    try:
        response = llm_with_tools.invoke(messages)

        # If the LLM made tool calls, execute them
        if response.tool_calls:
            tool_map = {t.name: t for t in tools}
            results = []
            public_summary = None
            internal_only = False
            internal_data = None
            for tool_call in response.tool_calls:
                tool_fn = tool_map.get(tool_call["name"])
                if tool_fn:
                    result = tool_fn.invoke(tool_call["args"])
                    results.append(result)
                    if tool_call["name"] == "evaluate_discount_request":
                        try:
                            payload = json.loads(str(result))
                            public_summary = payload.get("customer_safe_summary")
                            internal_only = True
                            # Use json.dumps for consistent JSON serialization (str() produces
                            # Python repr for dicts, not valid JSON).
                            internal_data = json.dumps(payload)
                        except Exception:
                            pass
                else:
                    results.append(f"Tool '{tool_call['name']}' not found in allowed tools.")

            raw_result = "\n".join(str(r) for r in results)
            if internal_only:
                # Keep cost/margin data out of AgentResponse.result so it is not included
                # in context compression or exposed in later LLM prompts / traces.
                # Langfuse still captures the full tool call via LLM invocation tracing.
                if role == "owner" and internal_data:
                    completed_task["status"] = "completed"
                    completed_task["result"] = internal_data
                    completed_task["internal_only"] = False
                    completed_task["public_summary"] = public_summary
                    completed_task["owner_bypass"] = True
                else:
                    result_text = public_summary or "Internal negotiation guidance completed."
                    agent_response = AgentResponse(
                        status="success",
                        confidence="high",
                        result=result_text,
                        facts=[result_text],
                        unknowns=[],
                    )
                    completed_task["status"] = "completed"
                    completed_task["result"] = agent_response.model_dump_json()
                    completed_task["internal_only"] = True
                    completed_task["public_summary"] = result_text
                    # internal_data is stored separately so approval_rules can check discount guidance
                    # without reading it from the compressed/logged result field.
                    # None means json.loads failed; approval_rules will fall back to result field.
                    completed_task["internal_data"] = internal_data
            else:
                agent_response = AgentResponse(
                    status="success",
                    confidence="high" if raw_result else "low",
                    result=raw_result or "No data found.",
                    facts=[raw_result] if raw_result else [],
                    unknowns=[] if raw_result else ["Requested data was empty or not found."],
                )
                completed_task["status"] = "completed"
                completed_task["result"] = agent_response.model_dump_json()
        else:
            # LLM responded without tool calls — use its text response
            agent_response = AgentResponse(
                status="partial",
                confidence="medium",
                result=str(response.content),
                unknowns=["Model returned text instead of calling a specific tool."],
            )
            completed_task["status"] = "completed"
            completed_task["result"] = agent_response.model_dump_json()

    except Exception as e:
        agent_response = AgentResponse(
            status="failed", confidence="low", result=f"Retrieval error: {e}", unknowns=[str(e)]
        )
        completed_task["status"] = "failed"
        completed_task["result"] = agent_response.model_dump_json()

    return {"completed_tasks": [completed_task]}
