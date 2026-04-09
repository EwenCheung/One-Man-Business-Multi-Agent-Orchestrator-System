"""
Test for Stage 4 — Reranking Quality (Cross-Encoder Reranker)

For every GT entry with labeled chunk IDs:
    1. Retrieve top-K via pgvector (search_policy_chunks)         → "before" list
    2. Rerank top-K with the cross-encoder (rerank_chunks)        → "after" list
    3. Evaluate Precision@N, Recall@N, MRR before vs. after reranking
    4. Compute Spearman ρ between vector order and reranked order (rank displacement)
    5. Measure per-step latency (search vs. rerank)

Optional consistency check:
    Runs the reranker N_CONSISTENCY_RUNS times on a small subset of queries and
    checks whether the output is identical each time.  Cross-encoders are
    deterministic, so this should always be 100%.

Metrics:
    Precision@N improvement     — P@N_after − P@N_before  (N = POLICY_TOP_N)
    Recall@N improvement        — R@N_after − R@N_before
    MRR improvement             — MRR_after − MRR_before
    Rank displacement (ρ)       — Spearman correlation between vector rank and reranker rank
                                  ρ≈1 → reranker preserves order (not reranking)
                                  ρ≈0 → reranker significantly reshuffles
    Reranking consistency       — % of repeated calls that produce identical output
    Latency cost                — ms/query for search step and rerank step separately

Output:
    tests/policy_agent/results/reranking_metrics.json
    tests/policy_agent/results/reranking_charts.png

Usage:
    uv run python tests/policy_agent/evaluate_reranking.py
    uv run python tests/policy_agent/evaluate_reranking.py --consistency-runs 3

Prerequisites:
    1. Connection to Supabase established
    2. Policies ingested
    3. Eval dependencies installed (uv sync --extra eval)
    4. Ground truth dataset present
    5. OPENAI_API_KEY set in .env  (embedding calls per query)
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
from scipy.stats import spearmanr

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PolicyChunk
from backend.tools.policy_tools import rerank_chunks, search_policy_chunks

# ── Paths ─────────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"


# ─── Metric helpers ───────────────────────────────────────────────────────────

def _metrics_at_n(chunks: list[dict], relevant: set[str], n: int) -> dict:
    """Precision@N, Recall@N, MRR over the first N items of a ranked list."""
    top = chunks[:n]
    hits = [1 if str(c["chunk_id"]) in relevant else 0 for c in top]
    precision = sum(hits) / n if top else 0.0
    recall = sum(hits) / len(relevant) if relevant else 0.0
    mrr = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
    return {"precision": _r(precision), "recall": _r(recall), "mrr": _r(mrr)}


def _spearman(top_k: list[dict], reranked: list[dict]) -> tuple[float | None, float | None]:
    """
    Spearman ρ between reranker order and the original vector order.
    Maps each reranked chunk to its position in the top-K vector list.
    ρ=1 → reranker preserves vector order; ρ<1 → reranker reshuffles.
    """
    vector_pos = {c["chunk_id"]: i for i, c in enumerate(top_k)}
    orig_positions = [vector_pos.get(c["chunk_id"], len(top_k)) for c in reranked]
    if len(orig_positions) < 2 or len(set(orig_positions)) < 2:
        return None, None
    rho, pval = spearmanr(range(len(orig_positions)), orig_positions)
    return float(rho), float(pval)


def _r(v: float, n: int = 4) -> float:
    return round(float(v), n)


# ─── Per-query evaluation ─────────────────────────────────────────────────────

def _evaluate_query(
    session,
    entry: dict,
    chunk_ids_in_db: set[str],
    top_k: int,
    top_n: int,
) -> dict | None:
    rel_ids = {str(cid) for cid in entry["relevant_chunk_ids"] if str(cid) in chunk_ids_in_db}
    if not rel_ids:
        return None

    query = entry["query"]

    # ── Search (vector retrieval) ─────────────────────────────────────────────
    t0 = time.perf_counter()
    top_k_chunks = search_policy_chunks(session, query, top_k=top_k)
    latency_search_ms = (time.perf_counter() - t0) * 1000

    if not top_k_chunks:
        return None

    # ── Rerank ───────────────────────────────────────────────────────────────
    t1 = time.perf_counter()
    try:
        reranked = rerank_chunks(query, top_k_chunks, top_n=top_n)
        rerank_failed = False
    except Exception as exc:
        print(f"    [WARN] rerank_chunks failed for {entry['query_id']}: {exc}")
        reranked = top_k_chunks[:top_n]   # fall back to vector order
        rerank_failed = True
    latency_rerank_ms = (time.perf_counter() - t1) * 1000

    # ── Before/after metrics ──────────────────────────────────────────────────
    before = _metrics_at_n(top_k_chunks, rel_ids, top_n)   # top-N of vector order
    after = _metrics_at_n(reranked, rel_ids, top_n)         # top-N of reranker order

    # ── Rank displacement ─────────────────────────────────────────────────────
    rho, pval = _spearman(top_k_chunks, reranked)

    return {
        "query_id": entry["query_id"],
        "category": entry["category"],
        "query_type": entry.get("query_type", ""),
        "n_relevant_in_db": len(rel_ids),
        "n_retrieved_k": len(top_k_chunks),
        "n_reranked_n": len(reranked),
        "rerank_failed": rerank_failed,
        # Before (top-N of vector order)
        "precision_before": before["precision"],
        "recall_before": before["recall"],
        "mrr_before": before["mrr"],
        # After (top-N of reranker)
        "precision_after": after["precision"],
        "recall_after": after["recall"],
        "mrr_after": after["mrr"],
        # Deltas
        "precision_delta": _r(after["precision"] - before["precision"]),
        "recall_delta": _r(after["recall"] - before["recall"]),
        "mrr_delta": _r(after["mrr"] - before["mrr"]),
        # Rank displacement
        "spearman_rho": _r(rho) if rho is not None else None,
        "spearman_pval": _r(pval) if pval is not None else None,
        # Chunk IDs for traceability
        "vector_order_ids": [str(c["chunk_id"]) for c in top_k_chunks],
        "reranked_ids": [str(c["chunk_id"]) for c in reranked],
        # Latency
        "latency_search_ms": _r(latency_search_ms, 1),
        "latency_rerank_ms": _r(latency_rerank_ms, 1),
        "latency_total_ms": _r(latency_search_ms + latency_rerank_ms, 1),
    }


# ─── Consistency check ────────────────────────────────────────────────────────

def _consistency_check(
    session,
    entries: list[dict],
    chunk_ids_in_db: set[str],
    top_k: int,
    top_n: int,
    n_runs: int,
    n_queries: int = 5,
) -> dict:
    """Run the reranker n_runs times on a small subset and check output stability."""
    subset = [e for e in entries
              if any(str(cid) in chunk_ids_in_db for cid in (e.get("relevant_chunk_ids") or []))]
    subset = subset[:n_queries]

    consistent_count = 0
    results = []
    print(f"  Consistency check: {n_runs} runs × {len(subset)} queries...")

    for entry in subset:
        query = entry["query"]
        top_k_chunks = search_policy_chunks(session, query, top_k=top_k)
        if not top_k_chunks:
            continue

        run_outputs: list[list[str]] = []
        for _ in range(n_runs):
            try:
                reranked = rerank_chunks(query, top_k_chunks, top_n=top_n)
                run_outputs.append([str(c["chunk_id"]) for c in reranked])
            except Exception:
                run_outputs.append([])

        is_consistent = all(r == run_outputs[0] for r in run_outputs[1:])
        if is_consistent:
            consistent_count += 1
        results.append({
            "query_id": entry["query_id"],
            "consistent": is_consistent,
            "outputs": run_outputs,
        })

    n_tested = len(results)
    return {
        "n_queries_tested": n_tested,
        "n_runs_per_query": n_runs,
        "consistent_queries": consistent_count,
        "consistency_rate_pct": _r(consistent_count / n_tested * 100) if n_tested else None,
        "per_query": results,
    }


# ─── Aggregation ─────────────────────────────────────────────────────────────

def _aggregate(per_query: list[dict]) -> tuple[dict, dict]:
    df = pd.DataFrame(per_query)

    def _agg(grp: pd.DataFrame) -> dict:
        spearman_vals = grp["spearman_rho"].dropna()
        return {
            "n": len(grp),
            "n_rerank_failures": int(grp["rerank_failed"].sum()),
            "precision_before": _r(float(grp["precision_before"].mean())),
            "precision_after": _r(float(grp["precision_after"].mean())),
            "precision_delta": _r(float(grp["precision_delta"].mean())),
            "recall_before": _r(float(grp["recall_before"].mean())),
            "recall_after": _r(float(grp["recall_after"].mean())),
            "recall_delta": _r(float(grp["recall_delta"].mean())),
            "mrr_before": _r(float(grp["mrr_before"].mean())),
            "mrr_after": _r(float(grp["mrr_after"].mean())),
            "mrr_delta": _r(float(grp["mrr_delta"].mean())),
            "mean_spearman_rho": _r(float(spearman_vals.mean())) if len(spearman_vals) else None,
            "latency_search_ms_mean": _r(float(grp["latency_search_ms"].mean()), 1),
            "latency_rerank_ms_mean": _r(float(grp["latency_rerank_ms"].mean()), 1),
            "latency_total_ms_mean": _r(float(grp["latency_total_ms"].mean()), 1),
            "latency_rerank_ms_p95": _r(float(grp["latency_rerank_ms"].quantile(0.95)), 1),
        }

    overall = _agg(df)
    per_category = {cat: _agg(grp) for cat, grp in df.groupby("category")}
    return overall, per_category


# ─── Plotting ─────────────────────────────────────────────────────────────────

def _make_charts(per_query: list[dict], overall: dict, per_category: dict) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    cats = [c for c in per_category if c != "out_of_domain"]
    x = np.arange(len(cats))
    w = 0.35

    # 1 — Precision@N before vs after by category
    ax = axes[0]
    before_p = [per_category[c]["precision_before"] for c in cats]
    after_p = [per_category[c]["precision_after"] for c in cats]
    ax.bar(x - w / 2, before_p, w, label="Before (vector top-N)", color="steelblue", alpha=0.8)
    ax.bar(x + w / 2, after_p, w, label="After (reranked)", color="mediumseagreen", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel(f"Precision@{settings.POLICY_TOP_N}")
    ax.set_title(f"Precision@{settings.POLICY_TOP_N} Before vs After Reranking")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.1)

    # 2 — MRR before vs after by category
    ax = axes[1]
    before_m = [per_category[c]["mrr_before"] for c in cats]
    after_m = [per_category[c]["mrr_after"] for c in cats]
    ax.bar(x - w / 2, before_m, w, label="Before", color="steelblue", alpha=0.8)
    ax.bar(x + w / 2, after_m, w, label="After", color="mediumseagreen", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("MRR")
    ax.set_title("MRR Before vs After Reranking")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.1)

    # 3 — Spearman ρ distribution (rank displacement)
    ax = axes[2]
    rhos = [r["spearman_rho"] for r in per_query if r.get("spearman_rho") is not None]
    if rhos:
        sns.histplot(rhos, bins=15, ax=ax, color="coral", binrange=(-1, 1))
        ax.axvline(float(np.mean(rhos)), color="red", linestyle="--",
                   label=f"mean ρ={np.mean(rhos):.3f}")
        ax.axvline(1.0, color="gray", linestyle=":", alpha=0.6, label="ρ=1 (no change)")
        ax.set_xlabel("Spearman ρ (reranker vs vector order)")
        ax.set_ylabel("Count")
        ax.legend(fontsize=8)
    ax.set_title("Rank Displacement Distribution\n(ρ=1 → no reorder; ρ<1 → reshuffled)")

    # 4 — Delta heatmap: Precision and MRR deltas by category
    ax = axes[3]
    delta_data = pd.DataFrame({
        "Category": cats,
        "ΔPrecision": [per_category[c]["precision_delta"] for c in cats],
        "ΔMRR": [per_category[c]["mrr_delta"] for c in cats],
        "ΔRecall": [per_category[c]["recall_delta"] for c in cats],
    }).set_index("Category")
    sns.heatmap(
        delta_data, annot=True, fmt=".3f",
        cmap="RdYlGn", center=0, linewidths=0.5, ax=ax,
        cbar_kws={"label": "Δ (after − before)"},
    )
    ax.set_title("Metric Improvement by Category\n(green = improvement, red = regression)")
    ax.tick_params(axis="x", rotation=15)
    ax.tick_params(axis="y", rotation=0)

    # 5 — Latency breakdown per query (scatter: search vs rerank)
    ax = axes[4]
    df = pd.DataFrame(per_query)
    ax.scatter(df["latency_search_ms"], df["latency_rerank_ms"],
               alpha=0.6, s=50, c="steelblue", edgecolors="none")
    ax.axhline(df["latency_rerank_ms"].mean(), color="red", linestyle="--",
               label=f"mean rerank={df['latency_rerank_ms'].mean():.0f} ms")
    ax.set_xlabel("Search latency (ms)")
    ax.set_ylabel("Rerank latency (ms)")
    ax.set_title("Per-Query Latency: Search vs Rerank")
    ax.legend(fontsize=8)

    # 6 — Overall delta summary bar
    ax = axes[5]
    metric_labels = ["ΔPrecision", "ΔRecall", "ΔMRR"]
    delta_vals = [overall["precision_delta"], overall["recall_delta"], overall["mrr_delta"]]
    colors = ["mediumseagreen" if v >= 0 else "salmon" for v in delta_vals]
    bars = ax.bar(metric_labels, delta_vals, color=colors, alpha=0.85, width=0.5)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Δ (after − before)")
    ax.set_title(f"Overall Reranking Improvement\n(N={settings.POLICY_TOP_N}, K={settings.POLICY_TOP_K})")
    for bar, val in zip(bars, delta_vals):
        ypos = bar.get_height() + 0.005 if val >= 0 else bar.get_height() - 0.025
        ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                f"{val:+.4f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle(
        f"Stage 4 — Reranking Quality  |  "
        f"K={settings.POLICY_TOP_K} → N={settings.POLICY_TOP_N}  |  "
        f"model={settings.RERANKER_MODEL}",
        fontsize=11, y=1.01,
    )
    plt.tight_layout()
    out = RESULTS_DIR / "reranking_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved        → {out}")


# ─── Summary printing ─────────────────────────────────────────────────────────

def _print_summary(
    overall: dict,
    per_category: dict,
    consistency: dict | None,
    n_eval: int,
    n_skipped: int,
) -> None:
    SEP = "=" * 66
    print(f"\n{SEP}")
    print("  STAGE 4 — RERANKING QUALITY SUMMARY")
    print(SEP)
    print(f"  Queries evaluated:  {n_eval}  (skipped {n_skipped})")
    print(f"  Config:  K={settings.POLICY_TOP_K} → N={settings.POLICY_TOP_N}  "
          f"model={settings.RERANKER_MODEL}")
    print()

    N = settings.POLICY_TOP_N
    print(f"  {'Metric':<20}  {'Before':>8}  {'After':>8}  {'Delta':>8}")
    print("  " + "-" * 50)
    for label, b_key, a_key, d_key in [
        (f"Precision@{N}", "precision_before", "precision_after", "precision_delta"),
        (f"Recall@{N}", "recall_before", "recall_after", "recall_delta"),
        ("MRR", "mrr_before", "mrr_after", "mrr_delta"),
    ]:
        delta = overall[d_key]
        sign = "+" if delta >= 0 else ""
        print(f"  {label:<20}  {overall[b_key]:>8.4f}  {overall[a_key]:>8.4f}  "
              f"{sign}{delta:>7.4f}")
    print()

    rho = overall.get("mean_spearman_rho")
    print(f"  Mean Spearman ρ:    {rho if rho is not None else 'n/a'}"
          f"  (1.0 = no reorder, 0 = full shuffle)")
    print(f"  Rerank failures:    {overall['n_rerank_failures']}/{n_eval}")
    print()

    print(f"  Latency (mean per query):")
    print(f"    Search:   {overall['latency_search_ms_mean']} ms")
    print(f"    Rerank:   {overall['latency_rerank_ms_mean']} ms  "
          f"(P95={overall['latency_rerank_ms_p95']} ms)")
    print(f"    Total:    {overall['latency_total_ms_mean']} ms")
    print()

    if consistency:
        cr = consistency.get("consistency_rate_pct")
        print(f"  Consistency check:  {cr}%  "
              f"({consistency['consistent_queries']}/{consistency['n_queries_tested']} queries "
              f"identical across {consistency['n_runs_per_query']} runs)")
        print()

    print("  Per-category (ΔP / ΔR / ΔMRR / mean ρ):")
    header = f"  {'Category':<22} {'N':>4}  {'ΔPrec':>7}  {'ΔRec':>7}  {'ΔMRR':>7}  {'mean ρ':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for cat, cm in per_category.items():
        rho_str = f"{cm['mean_spearman_rho']:.3f}" if cm["mean_spearman_rho"] is not None else "  n/a"
        print(
            f"  {cat:<22} {cm['n']:>4}  "
            f"{cm['precision_delta']:>+7.4f}  "
            f"{cm['recall_delta']:>+7.4f}  "
            f"{cm['mrr_delta']:>+7.4f}  "
            f"{rho_str:>7}"
        )
    print()
    _print_performance_summary(overall, per_category, consistency)
    print(SEP)


def _print_performance_summary(overall: dict, per_category: dict, consistency: dict | None) -> None:
    print("  Performance Summary:")
    N, K = settings.POLICY_TOP_N, settings.POLICY_TOP_K

    # Precision improvement
    p_delta = overall["precision_delta"]
    if p_delta > 0.05:
        print(f"  [OK]   Precision@{N} improved by {p_delta:+.4f} — reranker is adding value.")
    elif p_delta > 0:
        print(f"  [INFO] Precision@{N} improved marginally ({p_delta:+.4f}) — "
              "reranker helps but gains are small.")
    elif p_delta > -0.05:
        print(f"  [WARN] Precision@{N} unchanged/slightly worse ({p_delta:+.4f}) — "
              "reranker may not be worth the latency. Revisit prompt or consider removing it.")
    else:
        print(f"  [FAIL] Precision@{N} regressed ({p_delta:+.4f}) — "
              "reranker is hurting results. Revise the reranker prompt or model choice.")

    # MRR improvement
    mrr_delta = overall["mrr_delta"]
    if mrr_delta > 0.05:
        print(f"  [OK]   MRR improved by {mrr_delta:+.4f} — reranker surfaces relevant chunks earlier.")
    else:
        print(f"  [INFO] MRR delta={mrr_delta:+.4f} — minimal rank-ordering improvement.")

    # Rank displacement
    rho = overall.get("mean_spearman_rho")
    if rho is not None:
        if rho > 0.95:
            print(f"  [WARN] Mean Spearman ρ={rho:.3f} — reranker barely reorders results. "
                  "It may be agreeing with vector search instead of correcting it.")
        elif rho > 0.5:
            print(f"  [INFO] Mean Spearman ρ={rho:.3f} — moderate reordering.")
        else:
            print(f"  [OK]   Mean Spearman ρ={rho:.3f} — reranker significantly reshuffles "
                  "(verify this displacement correlates with metric improvement).")

    # Latency cost
    rerank_ms = overall["latency_rerank_ms_mean"]
    search_ms = overall["latency_search_ms_mean"]
    overhead_pct = rerank_ms / search_ms * 100 if search_ms else 0
    if rerank_ms > 2000:
        print(f"  [WARN] Reranking adds {rerank_ms:.0f} ms/query ({overhead_pct:.0f}% overhead). "
              f"Consider reducing POLICY_TOP_K={K} fed to the reranker, or using a faster model.")
    else:
        print(f"  [OK]   Reranking latency {rerank_ms:.0f} ms/query ({overhead_pct:.0f}% overhead).")

    # Consistency
    if consistency:
        cr = consistency.get("consistency_rate_pct")
        if cr is not None and cr < 100:
            print(f"  [WARN] Consistency rate={cr:.1f}% — reranker output varies across identical "
                  "calls despite temperature=0. Check LLM provider determinism.")
        elif cr == 100.0:
            print(f"  [OK]   Consistency 100% — reranker is fully deterministic at temp=0.")

    # Failures
    if overall["n_rerank_failures"] > 0:
        print(f"  [WARN] {overall['n_rerank_failures']} rerank failures (LLM returned invalid indices). "
              "Check structured output schema compatibility with the LLM.")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def evaluate_reranking(consistency_runs: int = 0) -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)
    top_k = settings.POLICY_TOP_K
    top_n = settings.POLICY_TOP_N

    # ── Load ground truth ──────────────────────────────────────────────────────
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth not found: {GT_PATH}")
    with open(GT_PATH) as f:
        gt_data = json.load(f)
    labeled = [e for e in gt_data["entries"] if e.get("relevant_chunk_ids")]
    print(f"Ground truth: {len(labeled)} labeled entries.")

    # ── Chunk IDs currently in DB ──────────────────────────────────────────────
    session = SessionLocal()
    try:
        chunk_ids_in_db: set[str] = {
            str(row[0]) for row in session.query(PolicyChunk.id).all()
        }
    finally:
        session.close()
    print(f"DB contains {len(chunk_ids_in_db)} chunks.  K={top_k}, N={top_n}.")

    # ── Evaluate each query ────────────────────────────────────────────────────
    per_query: list[dict] = []
    n_skipped = 0
    print(f"\nRunning search + rerank for {len(labeled)} queries...")

    session = SessionLocal()
    try:
        for i, entry in enumerate(labeled, start=1):
            if i % 10 == 0 or i == len(labeled):
                print(f"  [{i}/{len(labeled)}] {entry['query_id']} — {entry['category']}")
            result = _evaluate_query(session, entry, chunk_ids_in_db, top_k, top_n)
            if result is None:
                n_skipped += 1
            else:
                per_query.append(result)
    finally:
        session.close()

    if not per_query:
        raise RuntimeError("All queries skipped — chunk IDs in GT do not match current DB.")

    print(f"\nEvaluated {len(per_query)} queries, skipped {n_skipped}.")

    # ── Consistency check (optional) ───────────────────────────────────────────
    consistency: dict | None = None
    if consistency_runs >= 2:
        print(f"\nRunning consistency check ({consistency_runs} runs × 5 queries)...")
        session = SessionLocal()
        try:
            consistency = _consistency_check(
                session, labeled, chunk_ids_in_db,
                top_k, top_n, n_runs=consistency_runs, n_queries=5,
            )
        finally:
            session.close()

    # ── Aggregate ─────────────────────────────────────────────────────────────
    overall, per_category = _aggregate(per_query)

    # ── Assemble ──────────────────────────────────────────────────────────────
    metrics: dict = {
        "n_queries_evaluated": len(per_query),
        "n_queries_skipped": n_skipped,
        "overall": overall,
        "per_category": per_category,
        "consistency_check": consistency,
        "config_snapshot": {
            "POLICY_TOP_K": top_k,
            "POLICY_TOP_N": top_n,
            "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
            "RERANKER_MODEL": settings.RERANKER_MODEL,
        },
        "per_query": per_query,
    }

    # ── Save ──────────────────────────────────────────────────────────────────
    out_json = RESULTS_DIR / "reranking_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved       → {out_json}")

    # ── Plots + summary ───────────────────────────────────────────────────────
    _make_charts(per_query, overall, per_category)
    _print_summary(overall, per_category, consistency, len(per_query), n_skipped)

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 4: Reranking Quality Evaluation"
    )
    parser.add_argument(
        "--consistency-runs",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Run the reranker N times on a 5-query subset to check determinism "
            "(e.g. --consistency-runs 3). Requires N≥2. Adds N×5 extra LLM calls."
        ),
    )
    args = parser.parse_args()
    evaluate_reranking(consistency_runs=args.consistency_runs)
