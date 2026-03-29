"""
Test for Stage 5 — End-to-End Answer Quality (LLM Evaluation)

Runs the full policy agent pipeline (search → rerank → evaluate) for every GT
entry and measures the quality of the final PolicyDecision against the ground truth.

Base metrics (no additional LLM calls beyond the pipeline itself):
    Verdict accuracy           — % where decision.verdict == expected_verdict
    Hard constraint detection  — % of HC-positive GT entries correctly flagged
    Confidence calibration     — verdict accuracy stratified by confidence level
    not_covered false pos. rate — % of answerable queries misclassified as not_covered
    Faithfulness proxy         — word-overlap of supporting_rules against retrieved chunks
    Hallucination rate         — % of supporting_rules with < 40% word overlap with context

RAGAS metrics (--with-ragas, requires: uv sync --extra eval):
    faithfulness               — LLM judge: are answers grounded in retrieved context?
    answer_relevancy           — LLM judge: does the answer address the question?

Output:
    tests/policy_agent/results/answer_metrics.json
    tests/policy_agent/results/answer_charts.png

Usage:
    uv run python tests/policy_agent/evaluate_answers.py
    uv run python tests/policy_agent/evaluate_answers.py --with-ragas

Prerequisites:
    1. PostgreSQL + pgvector running
    2. Policies ingested
    3. Eval dependencies installed (uv sync --extra eval)
       Note: ragas depends on scikit-network which requires MSVC on Windows.
    4. Ground truth dataset present
    5. OPENAI_API_KEY set in .env
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
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix

from backend.agents.policy_agent import PolicyDecision, _evaluate
from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PolicyChunk
from backend.tools.policy_tools import rerank_chunks, search_policy_chunks
from backend.utils.llm_provider import get_chat_llm

# ── Paths ─────────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

VERDICT_LABELS = ["allowed", "disallowed", "requires_approval", "not_covered"]
FAITHFULNESS_THRESHOLD = 0.40   # word-overlap ratio below which a rule is flagged


# ─── Faithfulness proxy ───────────────────────────────────────────────────────

def _word_overlap(text_a: str, text_b: str) -> float:
    """Fraction of words in text_a that appear in text_b (case-insensitive)."""
    words_a = set(text_a.lower().split())
    if not words_a:
        return 0.0
    words_b = set(text_b.lower().split())
    return len(words_a & words_b) / len(words_a)


def _faithfulness_proxy(supporting_rules: list[str], context_texts: list[str]) -> dict:
    """
    Lightweight faithfulness check: for each supporting rule, compute the maximum
    word-overlap with any retrieved chunk. No LLM calls required.

    A rule is considered faithful if max_overlap >= FAITHFULNESS_THRESHOLD.
    Rules with low overlap are likely hallucinated or paraphrased beyond recognition.
    """
    if not supporting_rules:
        return {
            "n_rules": 0,
            "faithful": 0,
            "hallucinated": 0,
            "faithfulness_rate": None,
            "mean_max_overlap": None,
        }

    context_joined = " ".join(context_texts)
    scores = [
        max(
            (_word_overlap(rule, chunk) for chunk in context_texts),
            default=_word_overlap(rule, context_joined),
        )
        for rule in supporting_rules
    ]
    faithful = sum(1 for s in scores if s >= FAITHFULNESS_THRESHOLD)
    return {
        "n_rules": len(scores),
        "faithful": faithful,
        "hallucinated": len(scores) - faithful,
        "faithfulness_rate": _r(faithful / len(scores)) if scores else None,
        "mean_max_overlap": _r(float(np.mean(scores))) if scores else None,
    }


def _r(v: float, n: int = 4) -> float | None:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ─── Per-query evaluation ─────────────────────────────────────────────────────

def _run_query(session, entry: dict, llm) -> dict:
    """Run the full pipeline for one GT entry and return all per-query metrics."""
    query = entry["query"]
    sender_role = entry.get("sender_role", "customer")

    # Search
    t0 = time.perf_counter()
    candidates = search_policy_chunks(session, query)
    t_search = (time.perf_counter() - t0) * 1000

    # Rerank
    t1 = time.perf_counter()
    try:
        chunks = rerank_chunks(query, candidates)
    except Exception:
        chunks = candidates[: settings.POLICY_TOP_N]
    t_rerank = (time.perf_counter() - t1) * 1000

    # Evaluate
    t2 = time.perf_counter()
    decision: PolicyDecision = _evaluate(query, chunks, sender_role, llm)
    t_eval = (time.perf_counter() - t2) * 1000

    context_texts = [c["chunk_text"] for c in chunks]
    faith = _faithfulness_proxy(decision.supporting_rules, context_texts)

    exp_verdict = entry["expected_verdict"]
    exp_hc = entry["expected_hard_constraint"]

    return {
        # Identifiers
        "query_id": entry["query_id"],
        "query": query,
        "sender_role": sender_role,
        "category": entry["category"],
        "query_type": entry.get("query_type", ""),
        # Ground truth
        "expected_verdict": exp_verdict,
        "expected_hard_constraint": exp_hc,
        # PolicyDecision output
        "actual_verdict": decision.verdict,
        "actual_hard_constraint": decision.hard_constraint,
        "confidence": decision.confidence,
        "explanation": decision.explanation,
        "supporting_rules": decision.supporting_rules,
        "caveat": decision.caveat,
        # Context for ragas
        "context_texts": context_texts,
        # Correctness flags
        "verdict_correct": decision.verdict == exp_verdict,
        "hard_constraint_correct": decision.hard_constraint == exp_hc,
        "is_false_not_covered": (
            exp_verdict != "not_covered" and decision.verdict == "not_covered"
        ),
        # Faithfulness
        "n_supporting_rules": len(decision.supporting_rules),
        "faithfulness_rate": faith["faithfulness_rate"],
        "mean_overlap": faith["mean_max_overlap"],
        "n_hallucinated_rules": faith["hallucinated"],
        # Latency
        "latency_search_ms": _r(t_search, 1),
        "latency_rerank_ms": _r(t_rerank, 1),
        "latency_eval_ms": _r(t_eval, 1),
        "latency_total_ms": _r(t_search + t_rerank + t_eval, 1),
    }


# ─── RAGAS evaluation ─────────────────────────────────────────────────────────

def _run_ragas(per_query: list[dict]) -> dict:
    """
    Run ragas faithfulness and answer_relevancy over the full result set.
    Requires ragas to be installed (uv sync --extra eval).
    Uses OpenAI as the LLM judge (OPENAI_API_KEY must be set).
    """
    try:
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
        from datasets import Dataset
    except ImportError as exc:
        return {
            "computed": False,
            "error": (
                f"ragas or datasets not installed: {exc}. "
                "Run: uv sync --extra eval  "
                "(scikit-network requires MSVC on Windows — "
                "install from https://visualstudio.microsoft.com/visual-cpp-build-tools/)"
            ),
        }

    # Only evaluate rows that have retrieved context
    rows = [r for r in per_query if r["context_texts"]]
    if not rows:
        return {"computed": False, "error": "No rows with retrieved context."}

    print(f"  Running ragas on {len(rows)} queries (LLM-as-judge, uses OpenAI API)...")
    dataset = Dataset.from_dict({
        "question": [r["query"] for r in rows],
        "answer": [r["explanation"] for r in rows],
        "contexts": [r["context_texts"] for r in rows],
    })

    try:
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
        df = result.to_pandas()
        return {
            "computed": True,
            "n_queries": len(rows),
            "faithfulness_mean": _r(float(df["faithfulness"].mean())),
            "faithfulness_std": _r(float(df["faithfulness"].std())),
            "answer_relevancy_mean": _r(float(df["answer_relevancy"].mean())),
            "answer_relevancy_std": _r(float(df["answer_relevancy"].std())),
            "per_query": [
                {
                    "query_id": rows[i]["query_id"],
                    "faithfulness": _r(float(df["faithfulness"].iloc[i])),
                    "answer_relevancy": _r(float(df["answer_relevancy"].iloc[i])),
                }
                for i in range(len(rows))
            ],
        }
    except Exception as exc:
        return {"computed": False, "error": str(exc)}


# ─── Aggregation ─────────────────────────────────────────────────────────────

def _aggregate(per_query: list[dict]) -> dict:
    df = pd.DataFrame(per_query)

    # Verdict accuracy
    overall_acc = _r(float(df["verdict_correct"].mean() * 100))
    by_category = {
        cat: {
            "n": len(grp),
            "verdict_accuracy_pct": _r(float(grp["verdict_correct"].mean() * 100)),
            "mean_faithfulness_rate": _r(float(grp["faithfulness_rate"].dropna().mean()))
            if grp["faithfulness_rate"].notna().any() else None,
        }
        for cat, grp in df.groupby("category")
    }
    by_expected_verdict = {
        v: {
            "n": len(grp),
            "accuracy_pct": _r(float(grp["verdict_correct"].mean() * 100)),
        }
        for v, grp in df.groupby("expected_verdict")
        if len(grp) > 0
    }

    # Hard constraint detection
    hc_positive = df[df["expected_hard_constraint"] == True]
    hc_detection = {
        "n_expected_hard_constraint": len(hc_positive),
        "correctly_detected": int(hc_positive["hard_constraint_correct"].sum()),
        "detection_rate_pct": _r(float(hc_positive["hard_constraint_correct"].mean() * 100))
        if len(hc_positive) else None,
    }

    # Confidence calibration
    confidence_levels = ["high", "medium", "low"]
    calibration = {}
    for level in confidence_levels:
        grp = df[df["confidence"] == level]
        calibration[level] = {
            "n": len(grp),
            "verdict_accuracy_pct": _r(float(grp["verdict_correct"].mean() * 100))
            if len(grp) else None,
        }

    # not_covered false positive rate
    answerable = df[df["expected_verdict"] != "not_covered"]
    nc_fpr = {
        "n_answerable": len(answerable),
        "n_false_not_covered": int(answerable["is_false_not_covered"].sum()),
        "false_positive_rate_pct": _r(float(answerable["is_false_not_covered"].mean() * 100))
        if len(answerable) else None,
    }

    # Faithfulness proxy
    rules_df = df[df["n_supporting_rules"] > 0]
    total_rules = int(df["n_supporting_rules"].sum())
    total_hallucinated = int(df["n_hallucinated_rules"].sum())
    faithfulness_agg = {
        "method": "word_overlap_proxy",
        "threshold": FAITHFULNESS_THRESHOLD,
        "n_queries_with_rules": len(rules_df),
        "total_rules_evaluated": total_rules,
        "total_hallucinated_rules": total_hallucinated,
        "hallucination_rate_pct": _r(total_hallucinated / total_rules * 100)
        if total_rules else None,
        "mean_rule_coverage": _r(float(df["mean_overlap"].dropna().mean()))
        if df["mean_overlap"].notna().any() else None,
    }

    # Latency
    latency = {
        "search_ms_mean": _r(float(df["latency_search_ms"].mean()), 1),
        "rerank_ms_mean": _r(float(df["latency_rerank_ms"].mean()), 1),
        "eval_ms_mean": _r(float(df["latency_eval_ms"].mean()), 1),
        "total_ms_mean": _r(float(df["latency_total_ms"].mean()), 1),
        "total_ms_p95": _r(float(df["latency_total_ms"].quantile(0.95)), 1),
    }

    return {
        "verdict_accuracy": {
            "overall_pct": overall_acc,
            "by_category": by_category,
            "by_expected_verdict": by_expected_verdict,
        },
        "hard_constraint_detection": hc_detection,
        "confidence_calibration": calibration,
        "not_covered_false_positive": nc_fpr,
        "faithfulness_proxy": faithfulness_agg,
        "latency": latency,
    }


# ─── Plotting ─────────────────────────────────────────────────────────────────

def _make_charts(per_query: list[dict], aggregated: dict, ragas_result: dict) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    df = pd.DataFrame(per_query)

    # 1 — Confusion matrix (expected vs actual verdict)
    ax = axes[0]
    y_true = df["expected_verdict"].tolist()
    y_pred = df["actual_verdict"].tolist()
    present = sorted(set(y_true + y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=present)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=present)
    disp.plot(ax=ax, colorbar=False, cmap="Blues")
    ax.set_title("Verdict Confusion Matrix\n(rows=expected, cols=actual)")
    ax.tick_params(axis="x", rotation=30)

    # 2 — Verdict accuracy by category
    ax = axes[1]
    cat_data = aggregated["verdict_accuracy"]["by_category"]
    cats = list(cat_data.keys())
    accs = [cat_data[c]["verdict_accuracy_pct"] or 0 for c in cats]
    colors = ["mediumseagreen" if a >= 80 else "coral" if a < 60 else "goldenrod" for a in accs]
    bars = ax.bar(cats, accs, color=colors, alpha=0.85)
    ax.axhline(aggregated["verdict_accuracy"]["overall_pct"], color="red",
               linestyle="--", label=f"Overall={aggregated['verdict_accuracy']['overall_pct']:.1f}%")
    ax.set_ylim(0, 110)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Verdict Accuracy (%)")
    ax.set_title("Verdict Accuracy by Category")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, accs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=8)

    # 3 — Confidence calibration: accuracy per confidence level
    ax = axes[2]
    cal = aggregated["confidence_calibration"]
    levels = ["high", "medium", "low"]
    cal_accs = [cal[l]["verdict_accuracy_pct"] or 0 for l in levels]
    cal_ns = [cal[l]["n"] for l in levels]
    bar_colors = ["mediumseagreen", "goldenrod", "coral"]
    bars = ax.bar(levels, cal_accs, color=bar_colors, alpha=0.85)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Verdict Accuracy (%)")
    ax.set_title("Confidence Calibration\n(well-calibrated: high > medium > low)")
    for bar, val, n in zip(bars, cal_accs, cal_ns):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%\n(n={n})", ha="center", va="bottom", fontsize=8)

    # 4 — Faithfulness proxy per category
    ax = axes[3]
    cats_faith = [c for c in cats if c != "out_of_domain"]
    faith_vals = [
        (cat_data[c].get("mean_faithfulness_rate") or 0) * 100
        for c in cats_faith
    ]
    hall_rate = aggregated["faithfulness_proxy"]["hallucination_rate_pct"] or 0
    ax.bar(cats_faith, faith_vals, color="steelblue", alpha=0.85,
           label="Mean faithfulness rate (%)")
    ax.axhline(100 - hall_rate, color="red", linestyle="--",
               label=f"Overall faithfulness={(100-hall_rate):.1f}%")
    ax.set_xticklabels(cats_faith, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Faithfulness rate (%)")
    ax.set_title(f"Supporting Rules Faithfulness by Category\n"
                 f"(threshold=word_overlap≥{FAITHFULNESS_THRESHOLD})")
    ax.legend(fontsize=8)

    # 5 — Verdict accuracy by expected verdict type
    ax = axes[4]
    by_v = aggregated["verdict_accuracy"]["by_expected_verdict"]
    v_labels = list(by_v.keys())
    v_accs = [by_v[v]["accuracy_pct"] or 0 for v in v_labels]
    v_ns = [by_v[v]["n"] for v in v_labels]
    bars = ax.bar(v_labels, v_accs, color="mediumpurple", alpha=0.85)
    ax.set_ylim(0, 110)
    ax.set_xticklabels(v_labels, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Verdict Accuracy by GT Verdict Type")
    for bar, val, n in zip(bars, v_accs, v_ns):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%\n(n={n})", ha="center", va="bottom", fontsize=8)

    # 6 — Overall summary scorecard
    ax = axes[5]
    ax.axis("off")
    nc_fpr = aggregated["not_covered_false_positive"]["false_positive_rate_pct"] or 0
    hc_det = aggregated["hard_constraint_detection"]["detection_rate_pct"] or 0
    faith_mean = (aggregated["faithfulness_proxy"]["mean_rule_coverage"] or 0) * 100
    hall_rate_pct = aggregated["faithfulness_proxy"]["hallucination_rate_pct"] or 0
    overall_acc = aggregated["verdict_accuracy"]["overall_pct"] or 0

    scorecard_lines = [
        ("Verdict accuracy", f"{overall_acc:.1f}%"),
        ("HC detection rate", f"{hc_det:.1f}%"),
        ("not_covered FP rate", f"{nc_fpr:.1f}%"),
        ("Mean rule coverage", f"{faith_mean:.1f}%"),
        ("Hallucination rate", f"{hall_rate_pct:.1f}%"),
        ("Total queries", str(len(per_query))),
    ]
    if ragas_result.get("computed"):
        scorecard_lines += [
            ("RAGAS faithfulness", f"{ragas_result['faithfulness_mean']:.3f}"),
            ("RAGAS ans. relevancy", f"{ragas_result['answer_relevancy_mean']:.3f}"),
        ]
    col_labels = ["Metric", "Value"]
    table = ax.table(
        cellText=scorecard_lines,
        colLabels=col_labels,
        cellLoc="left",
        loc="center",
        bbox=[0.05, 0.1, 0.9, 0.85],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#4472C4")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#E8F0FE")
    ax.set_title("Overall Scorecard", fontweight="bold", pad=10)

    fig.suptitle(
        f"Stage 5 — End-to-End Answer Quality  |  "
        f"model={settings.OPENAI_MODEL}  |  n={len(per_query)} queries",
        fontsize=11, y=1.01,
    )
    plt.tight_layout()
    out = RESULTS_DIR / "answer_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved        → {out}")


# ─── Summary printing ─────────────────────────────────────────────────────────

def _print_summary(aggregated: dict, ragas_result: dict, n_eval: int) -> None:
    SEP = "=" * 66
    print(f"\n{SEP}")
    print("  STAGE 5 — END-TO-END ANSWER QUALITY SUMMARY")
    print(SEP)
    print(f"  Queries evaluated:  {n_eval}  |  model={settings.OPENAI_MODEL}")
    print()

    acc = aggregated["verdict_accuracy"]
    print(f"  Verdict accuracy:   {acc['overall_pct']:.1f}%  (overall)")
    print("  By expected verdict:")
    for v, vd in acc["by_expected_verdict"].items():
        print(f"    {v:<22}  {vd['accuracy_pct']:.1f}%  (n={vd['n']})")
    print()

    hc = aggregated["hard_constraint_detection"]
    print(f"  Hard-constraint detection:  {hc['detection_rate_pct']:.1f}%  "
          f"({hc['correctly_detected']}/{hc['n_expected_hard_constraint']})")
    print()

    cal = aggregated["confidence_calibration"]
    print("  Confidence calibration:")
    for level in ["high", "medium", "low"]:
        acc_val = cal[level]["verdict_accuracy_pct"]
        print(f"    {level:<8}  n={cal[level]['n']:>3}  "
              f"accuracy={f'{acc_val:.1f}%' if acc_val is not None else 'n/a'}")
    print()

    nc = aggregated["not_covered_false_positive"]
    print(f"  not_covered FP rate:  {nc['false_positive_rate_pct']:.1f}%  "
          f"({nc['n_false_not_covered']}/{nc['n_answerable']} answerable queries)")
    print()

    faith = aggregated["faithfulness_proxy"]
    print(f"  Faithfulness proxy (word-overlap ≥ {faith['threshold']}):")
    print(f"    Rules evaluated:  {faith['total_rules_evaluated']}")
    print(f"    Hallucinated:     {faith['total_hallucinated_rules']}  "
          f"({faith['hallucination_rate_pct']:.1f}%)")
    print(f"    Mean coverage:    {(faith['mean_rule_coverage'] or 0) * 100:.1f}%")
    print()

    if ragas_result.get("computed"):
        print(f"  RAGAS (LLM-as-judge, n={ragas_result['n_queries']}):")
        print(f"    Faithfulness:      {ragas_result['faithfulness_mean']:.3f}"
              f"  ± {ragas_result['faithfulness_std']:.3f}")
        print(f"    Answer relevancy:  {ragas_result['answer_relevancy_mean']:.3f}"
              f"  ± {ragas_result['answer_relevancy_std']:.3f}")
    elif ragas_result.get("error"):
        print(f"  RAGAS: not computed — {ragas_result['error']}")
    print()

    lat = aggregated["latency"]
    print(f"  Latency (mean/query):  "
          f"search={lat['search_ms_mean']} ms  "
          f"rerank={lat['rerank_ms_mean']} ms  "
          f"eval={lat['eval_ms_mean']} ms  "
          f"total={lat['total_ms_mean']} ms  (P95={lat['total_ms_p95']} ms)")
    print()

    _print_performance_summary(aggregated, ragas_result)
    print(SEP)


def _print_performance_summary(aggregated: dict, ragas_result: dict) -> None:
    print("  Performance Summary:")

    # Verdict accuracy
    overall_acc = aggregated["verdict_accuracy"]["overall_pct"] or 0
    if overall_acc >= 85:
        print(f"  [OK]   Verdict accuracy {overall_acc:.1f}% — pipeline produces correct verdicts.")
    elif overall_acc >= 70:
        print(f"  [WARN] Verdict accuracy {overall_acc:.1f}% — investigate wrong categories "
              "(check Stage 1/2/3 metrics for low-performing domains).")
    else:
        print(f"  [FAIL] Verdict accuracy {overall_acc:.1f}% — evaluation prompt or retrieval "
              "needs significant revision.")

    # Hard constraint detection
    hc_rate = aggregated["hard_constraint_detection"]["detection_rate_pct"] or 0
    if hc_rate >= 90:
        print(f"  [OK]   HC detection rate {hc_rate:.1f}% — hard constraints reliably flagged.")
    else:
        print(f"  [WARN] HC detection rate {hc_rate:.1f}% — hard constraints are missed. "
              "Strengthen evaluation prompt to forbid overriding hard constraints.")

    # Confidence calibration
    cal = aggregated["confidence_calibration"]
    high_acc = cal["high"]["verdict_accuracy_pct"] or 0
    low_acc = cal["low"]["verdict_accuracy_pct"] or 0
    if high_acc > low_acc + 10:
        print(f"  [OK]   Confidence calibrated — high ({high_acc:.1f}%) > low ({low_acc:.1f}%).")
    else:
        print(f"  [WARN] Poor confidence calibration — high ({high_acc:.1f}%) ≈ low ({low_acc:.1f}%). "
              "Add confidence calibration instructions to the evaluation prompt.")

    # not_covered FP rate
    nc_fpr = aggregated["not_covered_false_positive"]["false_positive_rate_pct"] or 0
    if nc_fpr <= 5:
        print(f"  [OK]   not_covered FP rate {nc_fpr:.1f}% — agent correctly handles answerable queries.")
    else:
        print(f"  [WARN] not_covered FP rate {nc_fpr:.1f}% — agent over-abstains. "
              "Increase POLICY_TOP_K or improve chunking coverage for affected categories.")

    # Faithfulness / hallucination
    hall_rate = aggregated["faithfulness_proxy"]["hallucination_rate_pct"] or 0
    if hall_rate <= 15:
        print(f"  [OK]   Hallucination rate {hall_rate:.1f}% — supporting rules grounded in context.")
    else:
        print(f"  [WARN] Hallucination rate {hall_rate:.1f}% — supporting rules are being invented "
              "or heavily paraphrased. Tighten evaluation prompt to require direct quotes.")

    # RAGAS scores
    if ragas_result.get("computed"):
        rf = ragas_result["faithfulness_mean"] or 0
        ra = ragas_result["answer_relevancy_mean"] or 0
        if rf >= 0.80:
            print(f"  [OK]   RAGAS faithfulness={rf:.3f} — answers grounded in retrieved context.")
        else:
            print(f"  [WARN] RAGAS faithfulness={rf:.3f} — answers not fully grounded. "
                  "Evaluate prompt instruction 'Base your verdict ONLY on the excerpts'.")
        if ra >= 0.80:
            print(f"  [OK]   RAGAS answer relevancy={ra:.3f} — explanations address the question.")
        else:
            print(f"  [WARN] RAGAS answer relevancy={ra:.3f} — explanations are off-topic. "
                  "Check whether retrieved chunks are relevant to the query (Stage 3/4).")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def evaluate_answers(with_ragas: bool = False) -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)

    # ── Load ground truth ──────────────────────────────────────────────────────
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth not found: {GT_PATH}")
    with open(GT_PATH) as f:
        gt_data = json.load(f)
    entries = gt_data["entries"]
    print(f"Ground truth: {len(entries)} entries.")

    # ── Shared LLM instance ────────────────────────────────────────────────────
    llm = get_chat_llm(scope="policy", temperature=0.0)

    # ── Run full pipeline for every entry ──────────────────────────────────────
    per_query: list[dict] = []
    print(f"\nRunning full pipeline for {len(entries)} queries...")

    session = SessionLocal()
    try:
        for i, entry in enumerate(entries, start=1):
            if i % 10 == 0 or i == len(entries):
                print(f"  [{i}/{len(entries)}] {entry['query_id']} — {entry['category']}")
            try:
                result = _run_query(session, entry, llm)
                per_query.append(result)
            except Exception as exc:
                print(f"  [ERROR] {entry['query_id']}: {exc}")
    finally:
        session.close()

    print(f"\nCompleted {len(per_query)}/{len(entries)} queries.")

    # ── RAGAS evaluation (optional) ────────────────────────────────────────────
    ragas_result: dict = {"computed": False}
    if with_ragas:
        print("\nRunning RAGAS evaluation...")
        ragas_result = _run_ragas(per_query)

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    aggregated = _aggregate(per_query)

    # ── Assemble output ───────────────────────────────────────────────────────
    metrics: dict = {
        "n_queries_evaluated": len(per_query),
        "aggregated": aggregated,
        "ragas": ragas_result,
        "config_snapshot": {
            "POLICY_TOP_K": settings.POLICY_TOP_K,
            "POLICY_TOP_N": settings.POLICY_TOP_N,
            "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
            "OPENAI_MODEL": settings.OPENAI_MODEL,
            "faithfulness_threshold": FAITHFULNESS_THRESHOLD,
        },
        # Omit context_texts from per_query to keep JSON compact
        "per_query": [
            {k: v for k, v in r.items() if k != "context_texts"}
            for r in per_query
        ],
    }

    # ── Save ──────────────────────────────────────────────────────────────────
    out_json = RESULTS_DIR / "answer_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved       → {out_json}")

    # ── Plots + summary ───────────────────────────────────────────────────────
    _make_charts(per_query, aggregated, ragas_result)
    _print_summary(aggregated, ragas_result, len(per_query))

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 5: End-to-End Answer Quality Evaluation"
    )
    parser.add_argument(
        "--with-ragas",
        action="store_true",
        help=(
            "Also run ragas faithfulness and answer_relevancy metrics "
            "(LLM-as-judge, ~2 extra OpenAI calls per query). "
            "Requires: uv sync --extra eval  and MSVC on Windows."
        ),
    )
    args = parser.parse_args()
    evaluate_answers(with_ragas=args.with_ragas)
