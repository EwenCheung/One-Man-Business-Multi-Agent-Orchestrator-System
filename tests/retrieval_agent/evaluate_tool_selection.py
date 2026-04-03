"""
Test for Stage 1 — Tool Selection Accuracy

Evaluates whether the LLM picks the correct tool(s) for each task description,
given only the tools allowed by the sender's role.

Runs the pipeline up to and including llm_with_tools.invoke(messages), then
inspects response.tool_calls against the ground truth expected_tools.
Tools are built and bound to the LLM but never invoked — no database required.
This isolates LLM decision quality from SQL execution quality.

Metrics:
    exact_match_rate     — predicted_tools == expected_tools (set equality)
    precision_at_1       — first tool called is the correct one (single-tool cases)
    recall_rate          — |predicted ∩ expected| / |expected|
    hallucination_rate   — % cases with at least one unexpected tool call
    no_call_rate         — % cases where LLM returns no tool calls when one is expected
    boundary_integrity   — % boundary cases where RBAC correctly prevents forbidden calls

Boundary tests are excluded from exact_match/recall/hallucination aggregation
and evaluated separately under boundary_integrity.

Output:
    tests/retrieval_agent/results/tool_selection_metrics.json
    tests/retrieval_agent/results/tool_selection_charts.png

Usage:
    uv run python tests/retrieval_agent/evaluate_tool_selection.py

Prerequisites:
    1. Ground truth dataset present (run generate_ground_truth.py first)
    2. LLM API key set in .env
"""

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

from backend.agents.retrieval_agent import _build_tools_for_request, _get_llm

# ── Paths ─────────────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# Pass / warn thresholds (lower_is_better tools: threshold meaning is inverted)
THRESHOLDS = {
    "exact_match":    {"ok": 0.85, "warn": 0.70},
    "precision_at_1": {"ok": 0.90, "warn": 0.75},
    "recall":         {"ok": 0.85, "warn": 0.70},
    "hallucination":  {"ok": 0.10, "warn": 0.20},   # lower is better
    "no_call":        {"ok": 0.05, "warn": 0.15},    # lower is better
}


def _r(v, n: int = 4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ── Per-case evaluation ────────────────────────────────────────────────────────

def _base_fields(entry: dict) -> dict:
    return {
        "case_id": entry["case_id"],
        "role": entry["role"],
        "sender_id": entry["sender_id"],
        "task_description": entry["task_description"],
        "task_type": entry["task_type"],
        "expected_tools": entry["expected_tools"],
        "is_boundary_test": entry["is_boundary_test"],
        "boundary_type": entry.get("boundary_type"),
    }


def _evaluate_case(entry: dict, llm) -> dict:
    """Run tool selection for one GT entry; return per-case metrics."""
    role = entry["role"]
    sender_id = entry["sender_id"]
    description = entry["task_description"]
    expected = set(entry["expected_tools"])

    # Build role-scoped LangChain tools.
    # SessionLocal is captured in closures but not called until tool.invoke() —
    # construction requires no DB connection.
    try:
        tools = _build_tools_for_request(role, sender_id)
    except ValueError as e:
        return {
            **_base_fields(entry),
            "error": str(e),
            "predicted_tools": [],
            "exact_match": False,
            "precision_at_1": None,
            "recall": 0.0,
            "hallucinated_tools": [],
            "no_call": True,
            "latency_ms": None,
        }

    llm_with_tools = llm.bind_tools(tools)

    # Replicate the exact messages used in retrieval_agent() so the evaluation
    # tests the production prompt, not a synthetic one.
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

    t0 = time.perf_counter()
    try:
        response = llm_with_tools.invoke(messages)
    except Exception as exc:
        return {
            **_base_fields(entry),
            "error": str(exc),
            "predicted_tools": [],
            "exact_match": False,
            "precision_at_1": None,
            "recall": 0.0,
            "hallucinated_tools": [],
            "no_call": True,
            "latency_ms": None,
        }
    latency_ms = _r((time.perf_counter() - t0) * 1000, 1)

    predicted = [call["name"] for call in response.tool_calls]
    predicted_set = set(predicted)

    exact_match = predicted_set == expected
    recall = _r(len(predicted_set & expected) / len(expected)) if expected else 1.0
    hallucinated = sorted(predicted_set - expected)
    no_call = len(predicted) == 0

    # Precision@1: meaningful only for single-tool expected sets
    p1 = None
    if len(expected) == 1:
        p1 = 1.0 if (predicted and predicted[0] in expected) else 0.0

    return {
        **_base_fields(entry),
        "error": None,
        "predicted_tools": predicted,
        "exact_match": exact_match,
        "precision_at_1": p1,
        "recall": recall,
        "hallucinated_tools": hallucinated,
        "no_call": no_call,
        "latency_ms": latency_ms,
    }


# ── Aggregation ────────────────────────────────────────────────────────────────

def _aggregate(per_case: list[dict]) -> dict:
    df = pd.DataFrame(per_case)
    valid = df[df["error"].isna()]

    # Non-boundary cases drive the main metrics
    normal = valid[valid["is_boundary_test"] == False]
    boundary = valid[valid["is_boundary_test"] == True]

    def safe_mean(series) -> float | None:
        s = series.dropna()
        return _r(float(s.mean())) if len(s) else None

    overall = {
        "n_total": len(df),
        "n_valid": len(valid),
        "n_normal": len(normal),
        "n_boundary": len(boundary),
        "n_errors": int(df["error"].notna().sum()),
        # Core metrics — normal cases only
        "exact_match_rate": safe_mean(normal["exact_match"].astype(float)),
        "precision_at_1": safe_mean(
            normal[normal["precision_at_1"].notna()]["precision_at_1"]
        ),
        "recall_rate": safe_mean(normal["recall"]),
        "hallucination_rate": safe_mean(
            (normal["hallucinated_tools"].apply(len) > 0).astype(float)
        ),
        "no_call_rate": safe_mean(normal["no_call"].astype(float)),
        "mean_latency_ms": safe_mean(valid["latency_ms"]),
        "p95_latency_ms": (
            _r(float(valid["latency_ms"].dropna().quantile(0.95)), 1)
            if valid["latency_ms"].notna().any()
            else None
        ),
    }

    # Boundary integrity: RBAC prevents disallowed tools from being bound, so
    # the LLM must either call the expected (closest-allowed) tool or abstain.
    # Both outcomes are acceptable.
    if len(boundary):
        boundary_pass = boundary.apply(
            lambda r: set(r["predicted_tools"]) == set(r["expected_tools"]) or r["no_call"],
            axis=1,
        )
        overall["boundary_integrity_rate"] = _r(float(boundary_pass.mean()))
    else:
        overall["boundary_integrity_rate"] = None

    # Per-role breakdown (normal cases only)
    by_role: dict = {}
    for role, grp in normal.groupby("role"):
        by_role[role] = {
            "n": len(grp),
            "exact_match_rate": safe_mean(grp["exact_match"].astype(float)),
            "recall_rate": safe_mean(grp["recall"]),
            "hallucination_rate": safe_mean(
                (grp["hallucinated_tools"].apply(len) > 0).astype(float)
            ),
            "no_call_rate": safe_mean(grp["no_call"].astype(float)),
            "mean_latency_ms": safe_mean(grp["latency_ms"]),
        }

    # Per-task-type breakdown (normal cases only)
    by_task_type: dict = {}
    for tt, grp in normal.groupby("task_type"):
        by_task_type[tt] = {
            "n": len(grp),
            "exact_match_rate": safe_mean(grp["exact_match"].astype(float)),
            "recall_rate": safe_mean(grp["recall"]),
        }

    # Most-confused tool pairs: expected → what was actually called instead
    confusion: dict[str, dict[str, int]] = {}
    for _, row in normal[~normal["exact_match"]].iterrows():
        for exp in row["expected_tools"]:
            for pred in row["predicted_tools"]:
                if pred != exp:
                    confusion.setdefault(exp, {})
                    confusion[exp][pred] = confusion[exp].get(pred, 0) + 1

    return {
        "overall": overall,
        "by_role": by_role,
        "by_task_type": by_task_type,
        "confusion": confusion,
    }


# ── Charts ────────────────────────────────────────────────────────────────────

def _make_charts(per_case: list[dict], aggregated: dict) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    df = pd.DataFrame(per_case)
    normal = df[(df["error"].isna()) & (df["is_boundary_test"] == False)]
    by_role = aggregated["by_role"]
    roles = sorted(by_role.keys())

    # Panel 1 — Exact match rate per role
    ax = axes[0]
    exact_vals = [by_role[r]["exact_match_rate"] or 0 for r in roles]
    colors = [
        "mediumseagreen" if v >= THRESHOLDS["exact_match"]["ok"]
        else "goldenrod" if v >= THRESHOLDS["exact_match"]["warn"]
        else "coral"
        for v in exact_vals
    ]
    bars = ax.bar(roles, [v * 100 for v in exact_vals], color=colors, alpha=0.85)
    ax.axhline(
        THRESHOLDS["exact_match"]["ok"] * 100, color="green", linestyle="--",
        linewidth=1, label=f"OK ≥ {THRESHOLDS['exact_match']['ok']*100:.0f}%",
    )
    ax.axhline(
        THRESHOLDS["exact_match"]["warn"] * 100, color="orange", linestyle=":",
        linewidth=1, label=f"Warn ≥ {THRESHOLDS['exact_match']['warn']*100:.0f}%",
    )
    ax.set_ylim(0, 110)
    ax.set_ylabel("Exact Match Rate (%)")
    ax.set_title("Tool Exact Match Rate by Role\n(boundary cases excluded)")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, exact_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=9,
        )

    # Panel 2 — Recall per task type
    ax = axes[1]
    by_tt = aggregated["by_task_type"]
    task_types = sorted(by_tt.keys())
    recall_vals = [by_tt[tt]["recall_rate"] or 0 for tt in task_types]
    bars = ax.bar(task_types, [v * 100 for v in recall_vals], color="steelblue", alpha=0.85)
    ax.axhline(
        THRESHOLDS["recall"]["ok"] * 100, color="green", linestyle="--",
        linewidth=1, label=f"OK ≥ {THRESHOLDS['recall']['ok']*100:.0f}%",
    )
    ax.set_ylim(0, 110)
    ax.set_xticklabels(task_types, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Recall (%)")
    ax.set_title("Tool Recall Rate by Task Type")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, recall_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=8,
        )

    # Panel 3 — Hallucination + no-call rates per role (grouped bar)
    ax = axes[2]
    x = np.arange(len(roles))
    width = 0.35
    hall_vals = [by_role[r]["hallucination_rate"] or 0 for r in roles]
    nocall_vals = [by_role[r]["no_call_rate"] or 0 for r in roles]
    ax.bar(x - width / 2, [v * 100 for v in hall_vals], width,
           label="Hallucination rate", color="coral", alpha=0.85)
    ax.bar(x + width / 2, [v * 100 for v in nocall_vals], width,
           label="No-call rate", color="mediumpurple", alpha=0.85)
    ax.axhline(
        THRESHOLDS["hallucination"]["ok"] * 100, color="coral",
        linestyle="--", linewidth=1, alpha=0.7,
        label=f"Hall. OK ≤ {THRESHOLDS['hallucination']['ok']*100:.0f}%",
    )
    ax.axhline(
        THRESHOLDS["no_call"]["ok"] * 100, color="mediumpurple",
        linestyle="--", linewidth=1, alpha=0.7,
        label=f"No-call OK ≤ {THRESHOLDS['no_call']['ok']*100:.0f}%",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(roles)
    max_y = max(max(hall_vals + nocall_vals, default=0) * 100 + 15, 25)
    ax.set_ylim(0, max_y)
    ax.set_ylabel("Rate (%)")
    ax.set_title("Hallucination & No-Call Rates by Role")
    ax.legend(fontsize=7)

    # Panel 4 — Overall scorecard table
    ax = axes[3]
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

    scorecard = [
        ("Exact match rate",
         f"{_fmt_pct(overall['exact_match_rate'])}  {_tag(overall['exact_match_rate'], 'exact_match')}"),
        ("Precision@1",
         f"{_fmt_pct(overall['precision_at_1'])}  {_tag(overall['precision_at_1'], 'precision_at_1')}"),
        ("Recall rate",
         f"{_fmt_pct(overall['recall_rate'])}  {_tag(overall['recall_rate'], 'recall')}"),
        ("Hallucination rate",
         f"{_fmt_pct(overall['hallucination_rate'])}  {_tag(overall['hallucination_rate'], 'hallucination', lower=True)}"),
        ("No-call rate",
         f"{_fmt_pct(overall['no_call_rate'])}  {_tag(overall['no_call_rate'], 'no_call', lower=True)}"),
        ("Boundary integrity",
         f"{_fmt_pct(overall.get('boundary_integrity_rate'))}  (n={overall['n_boundary']})"),
        ("Mean latency",   f"{overall['mean_latency_ms']} ms"),
        ("P95 latency",    f"{overall['p95_latency_ms']} ms"),
        ("Cases (normal)", str(overall["n_normal"])),
    ]
    table = ax.table(
        cellText=scorecard,
        colLabels=["Metric", "Value"],
        cellLoc="left",
        loc="center",
        bbox=[0.0, 0.05, 1.0, 0.92],
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

    fig.suptitle("Tool Selection Accuracy", fontsize=12, y=1.01)
    plt.tight_layout()
    out = RESULTS_DIR / "tool_selection_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved → {out}")


# ── Summary printing ──────────────────────────────────────────────────────────

def _print_summary(aggregated: dict) -> None:
    SEP = "=" * 66
    overall = aggregated["overall"]
    by_role = aggregated["by_role"]

    print(f"\n{SEP}")
    print("TOOL SELECTION ACCURACY SUMMARY")
    print(SEP)
    print(
        f"  Cases: {overall['n_valid']} valid  "
        f"({overall['n_normal']} normal  |  "
        f"{overall['n_boundary']} boundary  |  "
        f"{overall['n_errors']} errors)"
    )
    print()

    def _fmt(v, metric=None, lower=False):
        if v is None:
            return "n/a"
        pct = f"{v*100:.1f}%"
        if not metric:
            return pct
        ok, warn = THRESHOLDS[metric]["ok"], THRESHOLDS[metric]["warn"]
        tag = (
            "[OK]" if (v <= ok if lower else v >= ok)
            else "[WARN]" if (v <= warn if lower else v >= warn)
            else "[FAIL]"
        )
        return f"{pct}  {tag}"

    print(f"  Exact match rate:    {_fmt(overall['exact_match_rate'], 'exact_match')}")
    print(f"  Precision@1:         {_fmt(overall['precision_at_1'], 'precision_at_1')}")
    print(f"  Recall rate:         {_fmt(overall['recall_rate'], 'recall')}")
    print(f"  Hallucination rate:  {_fmt(overall['hallucination_rate'], 'hallucination', lower=True)}")
    print(f"  No-call rate:        {_fmt(overall['no_call_rate'], 'no_call', lower=True)}")
    print(f"  Boundary integrity:  {_fmt(overall.get('boundary_integrity_rate'))}  (n={overall['n_boundary']})")
    print(f"  Mean latency:        {overall['mean_latency_ms']} ms")
    print(f"  P95 latency:         {overall['p95_latency_ms']} ms")
    print()

    print("  Per-role breakdown (normal cases):")
    header = (
        f"  {'Role':<12}{'N':>4}  "
        f"{'Exact':>8}  {'Recall':>8}  {'Halluc':>8}  {'No-call':>8}  {'Latency':>10}"
    )
    print(header)
    print("  " + "-" * 64)
    for role in sorted(by_role.keys()):
        rd = by_role[role]
        print(
            f"  {role:<12}{rd['n']:>4}  "
            f"{_fmt(rd['exact_match_rate']):>8}  "
            f"{_fmt(rd['recall_rate']):>8}  "
            f"{_fmt(rd['hallucination_rate']):>8}  "
            f"{_fmt(rd['no_call_rate']):>8}  "
            f"{str(rd['mean_latency_ms']) + ' ms':>10}"
        )
    print()

    confusion = aggregated.get("confusion", {})
    if confusion:
        pairs = sorted(
            [(exp, pred, cnt) for exp, preds in confusion.items() for pred, cnt in preds.items()],
            key=lambda x: -x[2],
        )
        print("  Most-confused tool pairs (expected → called instead):")
        for exp, pred, cnt in pairs[:5]:
            print(f"    {exp} → {pred}:  {cnt} case(s)")
        print()


def _print_recommendations(aggregated: dict) -> None:
    overall = aggregated["overall"]
    em = overall["exact_match_rate"] or 0
    p1 = overall["precision_at_1"] or 0
    hall = overall["hallucination_rate"] or 0
    nocall = overall["no_call_rate"] or 0

    if em < THRESHOLDS["exact_match"]["warn"]:
        print("  [FAIL] Exact match low — review tool descriptions for ambiguity.")
    elif em < THRESHOLDS["exact_match"]["ok"]:
        print("  [WARN] Exact match borderline — inspect confused tool pairs above.")

    if p1 < THRESHOLDS["precision_at_1"]["warn"]:
        print("  [FAIL] Precision@1 low — LLM is not routing to the primary tool correctly.")
    elif p1 < THRESHOLDS["precision_at_1"]["ok"]:
        print("  [WARN] Precision@1 borderline — check system prompt tool-selection instruction.")

    if hall > THRESHOLDS["hallucination"]["warn"]:
        print("  [FAIL] Hallucination rate high — add 'call the SINGLE most relevant tool' "
              "to the system prompt.")
    elif hall > THRESHOLDS["hallucination"]["ok"]:
        print("  [WARN] Hallucination rate elevated — monitor closely.")

    if nocall > THRESHOLDS["no_call"]["warn"]:
        print("  [FAIL] No-call rate high — strengthen 'you MUST call a tool' instruction.")
    elif nocall > THRESHOLDS["no_call"]["ok"]:
        print("  [WARN] No-call rate elevated — check for ambiguous task descriptions.")


# ── Main ──────────────────────────────────────────────────────────────────────

def evaluate_tool_selection() -> dict:
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

    llm = _get_llm()
    per_case: list[dict] = []

    print(f"\nEvaluating tool selection for {len(entries)} cases (LLM only, no DB)...")
    for i, entry in enumerate(entries, start=1):
        if i % 10 == 0 or i == len(entries):
            print(f"  [{i}/{len(entries)}] {entry['case_id']} — {entry['role']}/{entry['task_type']}")
        per_case.append(_evaluate_case(entry, llm))

    print(f"\nCompleted {len(per_case)}/{len(entries)} cases.")

    aggregated = _aggregate(per_case)

    metrics = {
        "n_cases_evaluated": len(per_case),
        "aggregated": aggregated,
        "per_case": per_case,
    }

    out_json = RESULTS_DIR / "tool_selection_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"Metrics saved → {out_json}")

    _make_charts(per_case, aggregated)
    _print_summary(aggregated)
    _print_recommendations(aggregated)

    return metrics


if __name__ == "__main__":
    evaluate_tool_selection()
