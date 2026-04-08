"""
Test for Stage 2 — End-to-End Result Quality

Runs the full retrieval_agent() pipeline for every GT entry and evaluates
the quality of the final result against ground truth.

Base metrics (no extra LLM calls beyond the pipeline itself):
    task_completion_rate     — status == "completed"
    result_non_empty_rate    — result.strip() is non-empty for completed tasks
    field_coverage_rate      — % of expected_fields_present found in result text
    forbidden_field_rate     — % of results containing expected_fields_absent
                               (ZERO TOLERANCE — any non-zero value is a FAIL)

LLM-as-judge metrics (opt-in via --with-judge):
    relevance_score          — does the result directly answer the task? (1–5 scale)
    completeness_score       — does it include everything needed? (1–5 scale)
    semantic_leakage_rate    — % non-investor results judged to contain
                               confidential financial data in any form

Output:
    tests/retrieval_agent/results/end_to_end_metrics.json
    tests/retrieval_agent/results/end_to_end_charts.png

Usage:
    uv run python tests/retrieval_agent/evaluate_end_to_end.py
    uv run python tests/retrieval_agent/evaluate_end_to_end.py --with-judge

Prerequisites:
    1. Ground truth dataset present (run generate_ground_truth.py first)
    2. PostgreSQL running and seeded
    3. LLM API key set in .env
"""

import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.agents.retrieval_agent import retrieval_agent
from backend.utils.llm_provider import get_chat_llm

# ── Paths ─────────────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# Pass / warn thresholds
THRESHOLDS = {
    "completion":         {"ok": 0.95, "warn": 0.85},
    "field_coverage":     {"ok": 0.90, "warn": 0.80},
    "relevance":          {"ok": 0.80, "warn": 0.65},
    "completeness_judge": {"ok": 0.75, "warn": 0.60},
}


def _r(v, n: int = 4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ── LLM-as-judge Pydantic schemas ─────────────────────────────────────────────

class _RelevanceScore(BaseModel):
    relevance: int      # 1–5: does the result directly answer the task?
    completeness: int   # 1–5: does it include all information needed?
    reasoning: str


class _LeakageScore(BaseModel):
    leakage_detected: bool
    evidence: str       # quoted text constituting leakage, or "none"


# ── Build SubTask ──────────────────────────────────────────────────────────────

def _make_task(entry: dict) -> dict:
    """Build a SubTask dict from a ground truth entry."""
    return {
        "task_id": entry["case_id"],
        "description": entry["task_description"],
        "assignee": "retriever",
        "status": "pending",
        "result": "",
        "priority": "required",
        "context_needed": [],
        "injected_context": {
            "sender_role": entry["role"],
            "sender_id": entry["sender_id"],
        },
    }


# ── Judge helpers ─────────────────────────────────────────────────────────────

def _judge_relevance(
    judge_llm, description: str, role: str, result_text: str
) -> _RelevanceScore:
    structured = judge_llm.with_structured_output(_RelevanceScore)
    messages = [
        SystemMessage(content=(
            "You are a QA evaluator assessing a business data retrieval system.\n"
            "Score the result on two criteria using a 1–5 integer scale:\n"
            "  relevance:    1 = completely off-topic or wrong data type,\n"
            "                5 = directly answers the task with the right data\n"
            "  completeness: 1 = missing most needed information,\n"
            "                5 = all requested information is present\n\n"
            "Be strict:\n"
            "- A result returning catalog data when orders were requested → relevance=1\n"
            "- A result missing key fields (e.g. order status) → completeness ≤ 3\n"
            "- An empty result or 'data not available' → relevance=1, completeness=1\n"
            "Return valid JSON matching the schema exactly."
        )),
        HumanMessage(content=(
            f"Role: {role}\n"
            f"Task: {description}\n\n"
            f"Result (first 1500 chars):\n{result_text[:1500]}\n\n"
            "Score relevance and completeness."
        )),
    ]
    return structured.invoke(messages)


def _judge_leakage(judge_llm, role: str, result_text: str) -> _LeakageScore:
    structured = judge_llm.with_structured_output(_LeakageScore)
    messages = [
        SystemMessage(content=(
            "You are a security auditor reviewing retrieval results for data leakage.\n"
            "Check whether the result contains confidential financial data that should "
            "not be visible to this user role.\n\n"
            "Confidential data includes:\n"
            "  - Exact cost prices or wholesale prices\n"
            "  - Internal margin percentages\n"
            "  - Supplier source pricing\n"
            "  - ROI or profitability figures\n\n"
            "Set leakage_detected=true if any of these appear, even if phrased indirectly "
            "(e.g. 'this product has a 40% margin').\n"
            "In 'evidence', quote the exact text that constitutes leakage, or write 'none'.\n"
            "Return valid JSON matching the schema exactly."
        )),
        HumanMessage(content=(
            f"User role: {role}\n"
            f"Result (first 1500 chars):\n{result_text[:1500]}\n\n"
            "Is any confidential financial data present?"
        )),
    ]
    return structured.invoke(messages)


# ── Per-case evaluation ────────────────────────────────────────────────────────

def _base_fields(entry: dict) -> dict:
    return {
        "case_id": entry["case_id"],
        "role": entry["role"],
        "sender_id": entry["sender_id"],
        "task_description": entry["task_description"],
        "task_type": entry["task_type"],
        "expected_tools": entry["expected_tools"],
        "expected_fields_present": entry["expected_fields_present"],
        "expected_fields_absent": entry["expected_fields_absent"],
        "is_boundary_test": entry["is_boundary_test"],
        "boundary_type": entry.get("boundary_type"),
    }


def _evaluate_case(entry: dict, judge_llm=None) -> dict:
    """Run the full retrieval_agent() pipeline and evaluate result quality."""
    task = _make_task(entry)
    expected_present = entry["expected_fields_present"]
    expected_absent = entry["expected_fields_absent"]
    role = entry["role"]

    t0 = time.perf_counter()
    try:
        output = retrieval_agent(task)
    except Exception as exc:
        return {
            **_base_fields(entry),
            "error": str(exc),
            "actual_status": "error",
            "completed": False,
            "result_non_empty": False,
            "field_coverage": 0.0,
            "forbidden_field_present": False,
            "forbidden_fields_found": [],
            "relevance_score": None,
            "completeness_score": None,
            "judge_reasoning": None,
            "semantic_leakage": None,
            "leakage_evidence": None,
            "latency_ms": None,
        }
    latency_ms = _r((time.perf_counter() - t0) * 1000, 1)

    completed = output["completed_tasks"][0]
    actual_status = completed["status"]
    result_text = completed.get("result", "") or ""

    # Unwrap the AgentResponse envelope.  completed["result"] is always serialized as
    # AgentResponse JSON; the actual retrieved data is nested inside AgentResponse.result.
    # All coverage, forbidden-field, and judge checks must operate on data_text so they
    # inspect the retrieved payload rather than the wrapper's metadata keys.
    data_text = result_text
    try:
        outer = json.loads(result_text)
        if isinstance(outer, dict) and "status" in outer and "result" in outer:
            data_text = outer["result"] or ""
    except (json.JSONDecodeError, TypeError):
        pass

    is_completed = actual_status == "completed"
    result_non_empty = bool(data_text.strip())

    # Field coverage: % of expected_fields_present keys found in the data payload.
    # Uses substring matching — sufficient since field names are short, unambiguous
    # identifiers (order_id, cost_price, etc.).
    if expected_present and data_text:
        data_lower = data_text.lower()
        present_hits = [f for f in expected_present if f.lower() in data_lower]
        field_coverage = len(present_hits) / len(expected_present)
    else:
        field_coverage = 1.0 if not expected_present else 0.0

    # Forbidden fields: any expected_fields_absent keys found in the data payload.
    # Zero tolerance — a non-empty list is a critical failure.
    # data_text is already unwrapped from the AgentResponse envelope above.
    forbidden_found: list[str] = []
    if expected_absent and data_text:

        def _keys_in_data(data: object) -> set[str]:
            """Collect all dict keys from a parsed data payload (list of dicts or dict)."""
            if isinstance(data, list):
                keys: set[str] = set()
                for item in data:
                    if isinstance(item, dict):
                        keys.update(item.keys())
                return keys
            if isinstance(data, dict):
                return set(data.keys())
            return set()

        try:
            data_payload = json.loads(data_text)
            found_keys = _keys_in_data(data_payload)
            forbidden_found = [f for f in expected_absent if f in found_keys]
        except (json.JSONDecodeError, TypeError):
            # data_text is plain text — fall back to substring matching.
            data_lower = data_text.lower()
            forbidden_found = [f for f in expected_absent if f.lower() in data_lower]

    # LLM-as-judge: relevance + completeness (completed results only)
    relevance_score = None
    completeness_score = None
    judge_reasoning = None
    if judge_llm and is_completed and result_non_empty:
        try:
            scored = _judge_relevance(judge_llm, entry["task_description"], role, data_text)
            relevance_score = _r(scored.relevance / 5)
            completeness_score = _r(scored.completeness / 5)
            judge_reasoning = scored.reasoning
        except Exception as exc:
            judge_reasoning = f"Judge error: {exc}"

    # LLM-as-judge: semantic leakage (non-investor roles only, completed results only)
    semantic_leakage = None
    leakage_evidence = None
    if judge_llm and role != "investor" and is_completed and result_non_empty:
        try:
            leak = _judge_leakage(judge_llm, role, data_text)
            semantic_leakage = leak.leakage_detected
            leakage_evidence = leak.evidence
        except Exception as exc:
            leakage_evidence = f"Leakage judge error: {exc}"

    return {
        **_base_fields(entry),
        "error": None,
        "actual_status": actual_status,
        # Preview the actual data payload, not the AgentResponse wrapper.
        "result_preview": data_text[:300],
        "completed": is_completed,
        "result_non_empty": result_non_empty,
        "field_coverage": _r(field_coverage),
        "forbidden_field_present": len(forbidden_found) > 0,
        "forbidden_fields_found": forbidden_found,
        "relevance_score": relevance_score,
        "completeness_score": completeness_score,
        "judge_reasoning": judge_reasoning,
        "semantic_leakage": semantic_leakage,
        "leakage_evidence": leakage_evidence,
        "latency_ms": latency_ms,
    }


# ── Aggregation ───────────────────────────────────────────────────────────────

def _aggregate(per_case: list[dict], with_judge: bool) -> dict:
    df = pd.DataFrame(per_case)
    valid = df[df["error"].isna()]
    completed_df = valid[valid["completed"] == True]

    def safe_mean(series) -> float | None:
        s = series.dropna()
        return _r(float(s.mean())) if len(s) else None

    overall: dict = {
        "n_total": len(df),
        "n_valid": len(valid),
        "n_errors": int(df["error"].notna().sum()),
        "task_completion_rate": safe_mean(valid["completed"].astype(float)),
        "result_non_empty_rate": (
            safe_mean(completed_df["result_non_empty"].astype(float))
            if len(completed_df) else None
        ),
        "field_coverage_rate": safe_mean(valid["field_coverage"]),
        "forbidden_field_rate": safe_mean(valid["forbidden_field_present"].astype(float)),
        "mean_latency_ms": safe_mean(valid["latency_ms"]),
        "p95_latency_ms": (
            _r(float(valid["latency_ms"].dropna().quantile(0.95)), 1)
            if valid["latency_ms"].notna().any() else None
        ),
    }

    if with_judge:
        overall["mean_relevance"] = safe_mean(valid["relevance_score"])
        overall["mean_completeness"] = safe_mean(valid["completeness_score"])
        non_inv = valid[valid["role"] != "investor"]
        leakage_vals = non_inv["semantic_leakage"].dropna()
        overall["semantic_leakage_rate"] = (
            _r(float(leakage_vals.astype(float).mean())) if len(leakage_vals) else None
        )
        overall["n_leakage_checked"] = int(len(leakage_vals))
    else:
        overall["mean_relevance"] = None
        overall["mean_completeness"] = None
        overall["semantic_leakage_rate"] = None
        overall["n_leakage_checked"] = 0

    # Per-role breakdown
    by_role: dict = {}
    for role, grp in valid.groupby("role"):
        by_role[role] = {
            "n": len(grp),
            "completion_rate": safe_mean(grp["completed"].astype(float)),
            "field_coverage_rate": safe_mean(grp["field_coverage"]),
            "forbidden_field_rate": safe_mean(grp["forbidden_field_present"].astype(float)),
            "mean_relevance": safe_mean(grp["relevance_score"]) if with_judge else None,
            "mean_completeness": safe_mean(grp["completeness_score"]) if with_judge else None,
            "mean_latency_ms": safe_mean(grp["latency_ms"]),
        }

    # Per-task-type breakdown
    by_task_type: dict = {}
    for tt, grp in valid.groupby("task_type"):
        by_task_type[tt] = {
            "n": len(grp),
            "completion_rate": safe_mean(grp["completed"].astype(float)),
            "field_coverage_rate": safe_mean(grp["field_coverage"]),
        }

    # Boundary test summary
    boundary = valid[valid["is_boundary_test"] == True]
    boundary_summary = {
        "n_boundary_cases": len(boundary),
        "completion_rate": safe_mean(boundary["completed"].astype(float)) if len(boundary) else None,
        "forbidden_field_rate": (
            safe_mean(boundary["forbidden_field_present"].astype(float)) if len(boundary) else None
        ),
    }

    # Worst-performing completed cases by field coverage
    worst: list[dict] = []
    if len(completed_df):
        worst = (
            completed_df.nsmallest(5, "field_coverage")
            [["case_id", "role", "task_type", "task_description", "field_coverage"]]
            .to_dict(orient="records")
        )

    return {
        "overall": overall,
        "by_role": by_role,
        "by_task_type": by_task_type,
        "boundary_summary": boundary_summary,
        "worst_cases": worst,
    }


# ── Charts ────────────────────────────────────────────────────────────────────

def _make_charts(per_case: list[dict], aggregated: dict, with_judge: bool) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    df = pd.DataFrame(per_case)
    valid = df[df["error"].isna()]
    by_role = aggregated["by_role"]
    roles = sorted(by_role.keys())

    # Panel 1 — Completion rate per role
    ax = axes[0]
    comp_vals = [by_role[r]["completion_rate"] or 0 for r in roles]
    colors = [
        "mediumseagreen" if v >= THRESHOLDS["completion"]["ok"]
        else "goldenrod" if v >= THRESHOLDS["completion"]["warn"]
        else "coral"
        for v in comp_vals
    ]
    bars = ax.bar(roles, [v * 100 for v in comp_vals], color=colors, alpha=0.85)
    ax.axhline(
        THRESHOLDS["completion"]["ok"] * 100, color="green", linestyle="--",
        linewidth=1, label=f"OK ≥ {THRESHOLDS['completion']['ok']*100:.0f}%",
    )
    ax.set_ylim(0, 110)
    ax.set_ylabel("Completion Rate (%)")
    ax.set_title("Task Completion Rate by Role")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, comp_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=9,
        )

    # Panel 2 — Field coverage by task type
    ax = axes[1]
    by_tt = aggregated["by_task_type"]
    task_types = sorted(by_tt.keys())
    cov_vals = [by_tt[tt]["field_coverage_rate"] or 0 for tt in task_types]
    bars = ax.bar(task_types, [v * 100 for v in cov_vals], color="steelblue", alpha=0.85)
    ax.axhline(
        THRESHOLDS["field_coverage"]["ok"] * 100, color="green", linestyle="--",
        linewidth=1, label=f"OK ≥ {THRESHOLDS['field_coverage']['ok']*100:.0f}%",
    )
    ax.set_ylim(0, 110)
    ax.set_xticklabels(task_types, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Field Coverage (%)")
    ax.set_title("Field Coverage Rate by Task Type")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, cov_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=8,
        )

    # Panel 3 — Relevance score distribution per role (judge only)
    ax = axes[2]
    if with_judge and valid["relevance_score"].notna().any():
        role_groups = [
            valid[valid["role"] == r]["relevance_score"].dropna() * 100
            for r in roles
        ]
        bp = ax.boxplot(
            role_groups, labels=roles, patch_artist=True,
            boxprops=dict(facecolor="lightsteelblue", alpha=0.7),
        )
        ax.axhline(
            THRESHOLDS["relevance"]["ok"] * 100, color="green", linestyle="--",
            linewidth=1, label=f"OK ≥ {THRESHOLDS['relevance']['ok']*100:.0f}%",
        )
        ax.set_ylim(0, 110)
        ax.set_ylabel("Relevance Score (%)")
        ax.set_title("LLM Judge: Relevance Score by Role")
        ax.legend(fontsize=8)
    else:
        ax.text(
            0.5, 0.5, "LLM judge not run\n(use --with-judge)",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=11, color="gray",
        )
        ax.set_title("LLM Judge: Relevance Score by Role")
        ax.axis("off")

    # Panel 4 — Mean latency per role
    ax = axes[3]
    lat_vals = [by_role[r]["mean_latency_ms"] or 0 for r in roles]
    bars = ax.bar(roles, lat_vals, color="mediumpurple", alpha=0.85)
    ax.set_ylabel("Mean Latency (ms)")
    ax.set_title("End-to-End Latency by Role")
    for bar, val in zip(bars, lat_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
            f"{val:.0f} ms", ha="center", va="bottom", fontsize=9,
        )

    # Panel 5 — Forbidden field rate per role (zero-tolerance)
    ax = axes[4]
    forb_vals = [by_role[r]["forbidden_field_rate"] or 0 for r in roles]
    colors = ["coral" if v > 0 else "mediumseagreen" for v in forb_vals]
    bars = ax.bar(roles, [v * 100 for v in forb_vals], color=colors, alpha=0.85)
    ax.set_ylim(0, max(max(forb_vals) * 100 + 10, 15))
    ax.set_ylabel("Forbidden Field Rate (%)")
    ax.set_title("Forbidden Field Leakage by Role\n(zero tolerance — any non-zero bar = FAIL)")
    for bar, val in zip(bars, forb_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, max(bar.get_height() + 0.5, 1),
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=9,
        )

    # Panel 6 — Overall scorecard table
    ax = axes[5]
    ax.axis("off")
    overall = aggregated["overall"]

    def _fmt_pct(v):
        return f"{v*100:.1f}%" if v is not None else "n/a"

    def _tag(v, metric, lower=False):
        if v is None:
            return ""
        ok, warn = THRESHOLDS[metric]["ok"], THRESHOLDS[metric]["warn"]
        if lower:
            return "[OK]" if v <= ok else "[WARN]" if v <= warn else "[FAIL]"
        return "[OK]" if v >= ok else "[WARN]" if v >= warn else "[FAIL]"

    def _zero_tag(v):
        if v is None:
            return ""
        return "[OK]" if v == 0.0 else "[FAIL]"

    scorecard = [
        ("Task completion rate",
         f"{_fmt_pct(overall['task_completion_rate'])}  {_tag(overall['task_completion_rate'], 'completion')}"),
        ("Field coverage rate",
         f"{_fmt_pct(overall['field_coverage_rate'])}  {_tag(overall['field_coverage_rate'], 'field_coverage')}"),
        ("Forbidden field rate",
         f"{_fmt_pct(overall['forbidden_field_rate'])}  {_zero_tag(overall['forbidden_field_rate'])}"),
        ("Mean relevance (judge)",
         f"{_fmt_pct(overall['mean_relevance'])}  "
         f"{_tag(overall['mean_relevance'], 'relevance') if overall['mean_relevance'] is not None else '(--with-judge)'}"),
        ("Mean completeness (judge)",
         f"{_fmt_pct(overall['mean_completeness'])}  "
         f"{_tag(overall['mean_completeness'], 'completeness_judge') if overall['mean_completeness'] is not None else '(--with-judge)'}"),
        ("Semantic leakage rate",
         f"{_fmt_pct(overall['semantic_leakage_rate'])}  {_zero_tag(overall['semantic_leakage_rate'])}"),
        ("Mean latency",    f"{overall['mean_latency_ms']} ms"),
        ("P95 latency",     f"{overall['p95_latency_ms']} ms"),
        ("Cases evaluated", str(overall["n_valid"])),
    ]
    table = ax.table(
        cellText=scorecard,
        colLabels=["Metric", "Value"],
        cellLoc="left",
        loc="center",
        bbox=[0.0, 0.0, 1.0, 1.0],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#4472C4")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#E8F0FE")
    ax.set_title("Overall Scorecard", fontweight="bold", pad=8)

    fig.suptitle("End-to-End Result Quality", fontsize=12, y=1.01)
    plt.tight_layout()
    out = RESULTS_DIR / "end_to_end_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved → {out}")


# ── Summary printing ──────────────────────────────────────────────────────────

def _print_summary(aggregated: dict, with_judge: bool) -> None:
    SEP = "=" * 66
    overall = aggregated["overall"]
    by_role = aggregated["by_role"]

    print(f"\n{SEP}")
    print("END-TO-END RESULT QUALITY SUMMARY")
    print(SEP)
    print(f"  Cases evaluated: {overall['n_valid']}  ({overall['n_errors']} errors)")
    print()

    def _fmt(v, metric=None, lower=False, zero_tol=False):
        if v is None:
            return "n/a"
        pct = f"{v*100:.1f}%"
        if zero_tol:
            return f"{pct}  {'[OK]' if v == 0.0 else '[FAIL]'}"
        if metric:
            ok, warn = THRESHOLDS[metric]["ok"], THRESHOLDS[metric]["warn"]
            tag = (
                "[OK]" if (v <= ok if lower else v >= ok)
                else "[WARN]" if (v <= warn if lower else v >= warn)
                else "[FAIL]"
            )
            return f"{pct}  {tag}"
        return pct

    print(f"  Task completion rate:    {_fmt(overall['task_completion_rate'], 'completion')}")
    print(f"  Field coverage rate:     {_fmt(overall['field_coverage_rate'], 'field_coverage')}")
    print(f"  Forbidden field rate:    {_fmt(overall['forbidden_field_rate'], zero_tol=True)}")
    if with_judge:
        print(f"  Mean relevance (judge):  {_fmt(overall['mean_relevance'], 'relevance')}")
        print(f"  Mean completeness:       {_fmt(overall['mean_completeness'], 'completeness_judge')}")
        print(f"  Semantic leakage rate:   {_fmt(overall['semantic_leakage_rate'], zero_tol=True)}")
    else:
        print("  LLM judge:               not run  (use --with-judge to enable)")
    print(f"  Mean latency:            {overall['mean_latency_ms']} ms")
    print(f"  P95 latency:             {overall['p95_latency_ms']} ms")
    print()

    print("  Per-role breakdown:")
    header = (
        f"  {'Role':<12}{'N':>4}  "
        f"{'Complt':>8}  {'FldCov':>8}  {'Forb':>6}  "
        f"{'Relev':>7}  {'Latency':>10}"
    )
    print(header)
    print("  " + "-" * 64)
    for role in sorted(by_role.keys()):
        rd = by_role[role]
        relev = _fmt(rd["mean_relevance"]) if with_judge else "n/a"
        print(
            f"  {role:<12}{rd['n']:>4}  "
            f"{_fmt(rd['completion_rate']):>8}  "
            f"{_fmt(rd['field_coverage_rate']):>8}  "
            f"{_fmt(rd['forbidden_field_rate']):>6}  "
            f"{relev:>7}  "
            f"{str(rd['mean_latency_ms']) + ' ms':>10}"
        )
    print()

    worst = aggregated.get("worst_cases", [])
    if worst:
        print("  Worst-performing completed cases (lowest field coverage):")
        for w in worst:
            cov = f"{w['field_coverage']*100:.1f}%" if w["field_coverage"] is not None else "n/a"
            print(f"    [{w['case_id']}] {w['role']} — {w['task_type']} — coverage={cov}")
            print(f"      \"{w['task_description'][:72]}\"")
        print()

    print(SEP)


def _print_recommendations(aggregated: dict, with_judge: bool) -> None:
    overall = aggregated["overall"]
    comp = overall["task_completion_rate"] or 0
    cov = overall["field_coverage_rate"] or 0
    forb = overall["forbidden_field_rate"] or 0

    if comp < THRESHOLDS["completion"]["warn"]:
        print("  [FAIL] Completion rate low — inspect error messages in the per_case JSON.")
    elif comp < THRESHOLDS["completion"]["ok"]:
        print("  [WARN] Completion rate borderline — review failed task descriptions.")

    if cov < THRESHOLDS["field_coverage"]["warn"]:
        print("  [FAIL] Field coverage low — likely wrong tool selection. "
              "Run (evaluate_tool_selection.py) to diagnose.")
    elif cov < THRESHOLDS["field_coverage"]["ok"]:
        print("  [WARN] Field coverage borderline — check worst-performing task types above.")

    if forb > 0:
        print("  [FAIL] Forbidden fields in results — CRITICAL. "
              "cost_price or margin data is leaking. "
              "Inspect retrieval_tools.py column selection immediately.")

    if with_judge:
        rel = overall.get("mean_relevance") or 0
        leak = overall.get("semantic_leakage_rate") or 0
        if rel < THRESHOLDS["relevance"]["warn"]:
            print("  [FAIL] Mean relevance low (judge) — results are not answering tasks. "
                  "Run to check tool selection accuracy first.")
        elif rel < THRESHOLDS["relevance"]["ok"]:
            print("  [WARN] Mean relevance borderline — improve tool descriptions.")
        if leak > 0:
            print("  [FAIL] Semantic leakage detected (judge) — confidential financial data "
                  "present in non-investor results in a non-literal form. "
                  "Review system prompt and tool result formatting.")


# ── Main ──────────────────────────────────────────────────────────────────────

def evaluate_end_to_end(with_judge: bool = False) -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)

    if not GT_PATH.exists():
        raise FileNotFoundError(
            f"Ground truth not found: {GT_PATH}\n"
            "Run: uv run python tests/retrieval_agent/generate_ground_truth.py"
        )

    with open(GT_PATH) as f:
        gt_data = json.load(f)
    entries = gt_data["entries"]
    print(f"Ground truth: {len(entries)} entries.")

    judge_llm = get_chat_llm(scope="retrieval", temperature=0.0) if with_judge else None
    if with_judge:
        print("LLM-as-judge: enabled (relevance, completeness, semantic leakage)")

    per_case: list[dict] = []
    print(f"\nRunning full retrieval_agent() for {len(entries)} cases...")
    for i, entry in enumerate(entries, start=1):
        if i % 10 == 0 or i == len(entries):
            print(f"  [{i}/{len(entries)}] {entry['case_id']} — {entry['role']}/{entry['task_type']}")
        per_case.append(_evaluate_case(entry, judge_llm=judge_llm))

    print(f"\nCompleted {len(per_case)}/{len(entries)} cases.")

    aggregated = _aggregate(per_case, with_judge=with_judge)

    metrics = {
        "n_cases_evaluated": len(per_case),
        "with_judge": with_judge,
        "aggregated": aggregated,
        # Omit result_preview from saved JSON to keep file size manageable
        "per_case": [
            {k: v for k, v in r.items() if k != "result_preview"}
            for r in per_case
        ],
    }

    out_json = RESULTS_DIR / "end_to_end_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"Metrics saved → {out_json}")

    _make_charts(per_case, aggregated, with_judge=with_judge)
    _print_summary(aggregated, with_judge=with_judge)
    _print_recommendations(aggregated, with_judge=with_judge)

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="End-to-End Result Quality Evaluation"
    )
    parser.add_argument(
        "--with-judge",
        action="store_true",
        help=(
            "Enable LLM-as-judge scoring of relevance, completeness, and "
            "semantic leakage (~3 extra LLM calls per case)."
        ),
    )
    args = parser.parse_args()
    evaluate_end_to_end(with_judge=args.with_judge)
