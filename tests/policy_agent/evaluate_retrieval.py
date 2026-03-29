"""
Test for Stage 3 — Retrieval Quality (Vector Search)

For every GT entry that has labeled relevant_chunk_ids, embeds the query and
runs the live pgvector cosine search (search_policy_chunks), then compares the
retrieved set against the ground-truth set.

Metrics computed at K = 3, 5, 10:
    Precision@K     — fraction of top-K retrieved that are relevant
    Recall@K        — fraction of relevant chunks that appear in top-K
    Hit Rate@K      — % of queries with ≥1 relevant chunk in top-K
    MRR             — Mean Reciprocal Rank of the first relevant chunk
    nDCG@K          — Normalised Discounted Cumulative Gain
    Mean sim (rel)  — avg similarity score of the relevant chunks (calibration)

Output:
    tests/policy_agent/results/retrieval_metrics.json
    tests/policy_agent/results/retrieval_charts.png

Usage:
    uv run python tests/policy_agent/evaluate_retrieval.py

Prerequisites:
    1. PostgreSQL + pgvector running
    2. Policies ingested
    3. Eval dependencies installed (uv sync --extra eval)
    4. Ground truth dataset present (tests/policy_agent/test_cases/ground_truth_dataset.json)
    5. OPENAI_API_KEY set in .env  (one embed call per GT query)
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
from sklearn.metrics import ndcg_score

from backend.db.engine import SessionLocal
from backend.tools.policy_tools import search_policy_chunks

# ── Constants ─────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"
K_VALUES = [3, 5, 10]
MAX_K = max(K_VALUES)


# ─── Metric functions ─────────────────────────────────────────────────────────

def _precision_at_k(retrieved: list[dict], relevant: set[int], k: int) -> float:
    top = retrieved[:k]
    return sum(1 for c in top if c["chunk_id"] in relevant) / k if top else 0.0


def _recall_at_k(retrieved: list[dict], relevant: set[int], k: int) -> float:
    if not relevant:
        return 0.0
    top = retrieved[:k]
    hits = sum(1 for c in top if c["chunk_id"] in relevant)
    return hits / len(relevant)


def _hit_rate_at_k(retrieved: list[dict], relevant: set[int], k: int) -> bool:
    return any(c["chunk_id"] in relevant for c in retrieved[:k])


def _mrr(retrieved: list[dict], relevant: set[int]) -> float:
    for rank, chunk in enumerate(retrieved, start=1):
        if chunk["chunk_id"] in relevant:
            return 1.0 / rank
    return 0.0


def _ndcg_at_k(retrieved: list[dict], relevant: set[int], k: int) -> float:
    """Binary-relevance nDCG over the top-K retrieved list."""
    top = retrieved[:k]
    if not top:
        return 0.0
    y_true = np.array([[1.0 if c["chunk_id"] in relevant else 0.0 for c in top]])
    y_score = np.array([[c["similarity_score"] for c in top]])
    if y_true.sum() == 0:
        return 0.0
    return float(ndcg_score(y_true, y_score, k=k))


def _r(v: float, n: int = 4) -> float:
    return round(float(v), n)


# ─── Per-query evaluation ─────────────────────────────────────────────────────

def _evaluate_query(
    session,
    entry: dict,
    chunk_ids_in_db: set[int],
) -> dict | None:
    """Run retrieval for one GT entry and return all metrics. Returns None if skipped."""
    rel_ids = {cid for cid in entry["relevant_chunk_ids"] if cid in chunk_ids_in_db}
    if not rel_ids:
        return None  # chunk IDs from this entry are not in current DB

    t0 = time.perf_counter()
    retrieved = search_policy_chunks(session, entry["query"], top_k=MAX_K)
    latency_ms = (time.perf_counter() - t0) * 1000

    rel_chunks = [c for c in retrieved if c["chunk_id"] in rel_ids]
    non_rel_chunks = [c for c in retrieved if c["chunk_id"] not in rel_ids]

    result = {
        "query_id": entry["query_id"],
        "category": entry["category"],
        "query_type": entry.get("query_type", ""),
        "n_relevant_in_db": len(rel_ids),
        "retrieved_chunk_ids": [c["chunk_id"] for c in retrieved],
        "latency_ms": _r(latency_ms, 1),
    }

    for k in K_VALUES:
        result[f"precision_at_{k}"] = _r(_precision_at_k(retrieved, rel_ids, k))
        result[f"recall_at_{k}"] = _r(_recall_at_k(retrieved, rel_ids, k))
        result[f"hit_rate_at_{k}"] = _hit_rate_at_k(retrieved, rel_ids, k)
        result[f"ndcg_at_{k}"] = _r(_ndcg_at_k(retrieved, rel_ids, k))

    result["mrr"] = _r(_mrr(retrieved, rel_ids))
    result["mean_sim_relevant"] = _r(
        float(np.mean([c["similarity_score"] for c in rel_chunks]))
        if rel_chunks else 0.0
    )
    result["mean_sim_non_relevant"] = _r(
        float(np.mean([c["similarity_score"] for c in non_rel_chunks]))
        if non_rel_chunks else 0.0
    )
    result["sim_gap"] = _r(result["mean_sim_relevant"] - result["mean_sim_non_relevant"])

    return result


# ─── Aggregation ─────────────────────────────────────────────────────────────

def _aggregate(per_query: list[dict]) -> dict:
    df = pd.DataFrame(per_query)

    def _cat_agg(grp: pd.DataFrame) -> dict:
        agg = {"n": len(grp)}
        for k in K_VALUES:
            agg[f"precision_at_{k}"] = _r(float(grp[f"precision_at_{k}"].mean()))
            agg[f"recall_at_{k}"] = _r(float(grp[f"recall_at_{k}"].mean()))
            agg[f"hit_rate_at_{k}_pct"] = _r(float(grp[f"hit_rate_at_{k}"].mean() * 100))
            agg[f"ndcg_at_{k}"] = _r(float(grp[f"ndcg_at_{k}"].mean()))
        agg["mrr"] = _r(float(grp["mrr"].mean()))
        agg["mean_sim_relevant"] = _r(float(grp["mean_sim_relevant"].mean()))
        agg["mean_sim_gap"] = _r(float(grp["sim_gap"].mean()))
        return agg

    overall = _cat_agg(df)
    overall["mean_latency_ms"] = _r(float(df["latency_ms"].mean()), 1)
    overall["p95_latency_ms"] = _r(float(df["latency_ms"].quantile(0.95)), 1)

    per_category = {
        cat: _cat_agg(grp)
        for cat, grp in df.groupby("category")
    }
    return overall, per_category


# ─── Plotting ─────────────────────────────────────────────────────────────────

def _make_charts(per_query: list[dict], overall: dict, per_category: dict) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    cats = [c for c in per_category if c != "out_of_domain"]
    x = np.arange(len(cats))
    w = 0.25

    # 1 — Precision@K by category
    ax = axes[0]
    for i, k in enumerate(K_VALUES):
        vals = [per_category[c].get(f"precision_at_{k}", 0) for c in cats]
        ax.bar(x + (i - 1) * w, vals, w, label=f"P@{k}")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Precision")
    ax.set_title("Precision@K by Category")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.05)

    # 2 — Recall@K by category
    ax = axes[1]
    for i, k in enumerate(K_VALUES):
        vals = [per_category[c].get(f"recall_at_{k}", 0) for c in cats]
        ax.bar(x + (i - 1) * w, vals, w, label=f"R@{k}")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Recall")
    ax.set_title("Recall@K by Category")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.05)

    # 3 — Hit Rate@K (at K=3 and K=5 and K=10) by category
    ax = axes[2]
    for i, k in enumerate(K_VALUES):
        vals = [per_category[c].get(f"hit_rate_at_{k}_pct", 0) for c in cats]
        ax.bar(x + (i - 1) * w, vals, w, label=f"HR@{k}")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("Hit Rate@K by Category")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 110)

    # 4 — MRR and nDCG@5 by category
    ax = axes[3]
    mrr_vals = [per_category[c].get("mrr", 0) for c in cats]
    ndcg_vals = [per_category[c].get("ndcg_at_5", 0) for c in cats]
    ax.bar(x - w / 2, mrr_vals, w, label="MRR", color="steelblue")
    ax.bar(x + w / 2, ndcg_vals, w, label="nDCG@5", color="mediumseagreen")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Score")
    ax.set_title("MRR and nDCG@5 by Category")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.05)

    # 5 — Similarity calibration: relevant vs non-relevant
    ax = axes[4]
    rel_vals = [per_category[c].get("mean_sim_relevant", 0) for c in cats]
    gap_vals = [per_category[c].get("mean_sim_gap", 0) for c in cats]
    ax.bar(x - w / 2, rel_vals, w, label="Mean sim (relevant)", color="steelblue")
    ax.bar(x + w / 2, gap_vals, w, label="Sim gap (rel−non-rel)", color="salmon")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Cosine similarity")
    ax.set_title("Retrieval Calibration by Category")
    ax.legend(fontsize=8)

    # 6 — Overall summary (radar-style bar of headline metrics)
    ax = axes[5]
    metric_labels = [f"P@{k}" for k in K_VALUES] + [f"R@{k}" for k in K_VALUES] + ["MRR", "nDCG@5"]
    metric_vals = (
        [overall.get(f"precision_at_{k}", 0) for k in K_VALUES]
        + [overall.get(f"recall_at_{k}", 0) for k in K_VALUES]
        + [overall.get("mrr", 0), overall.get("ndcg_at_5", 0)]
    )
    colors = (
        ["steelblue"] * len(K_VALUES)
        + ["mediumseagreen"] * len(K_VALUES)
        + ["coral", "mediumpurple"]
    )
    bars = ax.bar(range(len(metric_labels)), metric_vals, color=colors, alpha=0.85)
    ax.set_xticks(range(len(metric_labels)))
    ax.set_xticklabels(metric_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Score")
    ax.set_title("Overall Retrieval Metrics (all queries)")
    ax.set_ylim(0, 1.05)
    for bar, val in zip(bars, metric_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.2f}", ha="center", va="bottom", fontsize=7)

    from backend.config import settings
    fig.suptitle(
        f"Stage 3 — Retrieval Quality  |  "
        f"POLICY_TOP_K={settings.POLICY_TOP_K}  model={settings.EMBEDDING_MODEL}",
        fontsize=11, y=1.01,
    )
    plt.tight_layout()
    out = RESULTS_DIR / "retrieval_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved        → {out}")


# ─── Summary printing ─────────────────────────────────────────────────────────

def _print_summary(overall: dict, per_category: dict, n_eval: int, n_skipped: int) -> None:
    from backend.config import settings

    SEP = "=" * 64
    print(f"\n{SEP}")
    print("  STAGE 3 — RETRIEVAL QUALITY SUMMARY")
    print(SEP)
    print(f"  Queries evaluated:  {n_eval}  (skipped {n_skipped} — chunk IDs not in DB)")
    print(f"  POLICY_TOP_K={settings.POLICY_TOP_K}  evaluated at K={K_VALUES}")
    print(f"  Latency:  mean={overall['mean_latency_ms']} ms  P95={overall['p95_latency_ms']} ms")
    print()

    header = f"  {'Metric':<14}" + "".join(f"  {f'K={k}':>8}" for k in K_VALUES)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for metric, label in [("precision", "Precision"), ("recall", "Recall"),
                           ("hit_rate", "Hit Rate %"), ("ndcg", "nDCG")]:
        key_fn = (
            (lambda k: f"hit_rate_at_{k}_pct")
            if metric == "hit_rate"
            else (lambda k: f"{metric}_at_{k}")
        )
        row = f"  {label:<14}" + "".join(
            f"  {overall.get(key_fn(k), 0):>8.4f}" for k in K_VALUES
        )
        print(row)
    print(f"  {'MRR':<14}  {overall.get('mrr', 0):>8.4f}")
    print()

    print("  Per-category breakdown (P@5 / R@5 / HR@5 / MRR / nDCG@5):")
    header2 = f"  {'Category':<22} {'N':>4}  {'P@5':>6}  {'R@5':>6}  {'HR@5%':>7}  {'MRR':>6}  {'nDCG@5':>7}"
    print(header2)
    print("  " + "-" * (len(header2) - 2))
    for cat, cm in per_category.items():
        print(
            f"  {cat:<22} {cm['n']:>4}  "
            f"{cm.get('precision_at_5', 0):>6.3f}  "
            f"{cm.get('recall_at_5', 0):>6.3f}  "
            f"{cm.get('hit_rate_at_5_pct', 0):>6.1f}%  "
            f"{cm.get('mrr', 0):>6.3f}  "
            f"{cm.get('ndcg_at_5', 0):>7.3f}"
        )
    print()
    _print_performance_summary(overall, per_category)
    print(SEP)


def _print_performance_summary(overall: dict, per_category: dict) -> None:
    from backend.config import settings

    print("  Performance Summary:")

    # Recall@5 — the most important metric for RAG (we need the relevant chunk to BE retrieved)
    r5 = overall.get("recall_at_5", 0)
    if r5 >= 0.85:
        print(f"  [OK]   Recall@5={r5:.3f} — relevant chunks are reliably retrieved.")
    elif r5 >= 0.65:
        print(f"  [WARN] Recall@5={r5:.3f} — some relevant chunks are being missed; "
              f"consider increasing POLICY_TOP_K (currently {settings.POLICY_TOP_K}).")
    else:
        print(f"  [FAIL] Recall@5={r5:.3f} — most relevant chunks are not retrieved. "
              "Increase POLICY_TOP_K significantly or improve embedding model.")

    # Precision@5 — too-low = poor signal-to-noise for the reranker
    p5 = overall.get("precision_at_5", 0)
    if p5 >= 0.4:
        print(f"  [OK]   Precision@5={p5:.3f} — retrieval is relatively precise.")
    else:
        print(f"  [WARN] Precision@5={p5:.3f} — many retrieved chunks are irrelevant; "
              "category filters or a stronger embedding model may help.")

    # MRR — relevant chunk should appear early in the ranked list
    mrr = overall.get("mrr", 0)
    if mrr >= 0.75:
        print(f"  [OK]   MRR={mrr:.3f} — relevant chunk appears near the top of results.")
    elif mrr >= 0.50:
        print(f"  [WARN] MRR={mrr:.3f} — relevant chunk often appears mid-list; "
              "chunking granularity may be too coarse.")
    else:
        print(f"  [FAIL] MRR={mrr:.3f} — relevant chunk rarely surfaces early. "
              "Revisit chunk size or embedding model.")

    # Hit Rate@3 — must-have for tight reranker budgets
    hr3 = overall.get("hit_rate_at_3_pct", 0) / 100
    if hr3 >= 0.80:
        print(f"  [OK]   Hit Rate@3={hr3:.1%} — good top-3 coverage for reranker.")
    else:
        print(f"  [WARN] Hit Rate@3={hr3:.1%} — relevant chunk often not in top-3; "
              f"POLICY_TOP_K={settings.POLICY_TOP_K} may be too tight.")

    # nDCG@5
    ndcg5 = overall.get("ndcg_at_5", 0)
    if ndcg5 >= 0.70:
        print(f"  [OK]   nDCG@5={ndcg5:.3f} — retrieval ranking quality is good.")
    else:
        print(f"  [WARN] nDCG@5={ndcg5:.3f} — ranking quality is below threshold; "
              "consider HNSW index tuning (ef_construction, m) or a finer embedding model.")

    # Per-category worst performer
    cat_r5 = {c: v.get("recall_at_5", 0) for c, v in per_category.items()
               if c != "out_of_domain"}
    if cat_r5:
        worst_cat = min(cat_r5, key=cat_r5.get)
        if cat_r5[worst_cat] < 0.60:
            print(f"  [WARN] Worst category: '{worst_cat}' (Recall@5={cat_r5[worst_cat]:.3f}) — "
                  "that category's chunks may have chunking or embedding issues (check Stage 1/2).")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def evaluate_retrieval() -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)

    # ── Load ground truth ──────────────────────────────────────────────────────
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth not found: {GT_PATH}")
    with open(GT_PATH) as f:
        gt_data = json.load(f)

    labeled = [e for e in gt_data["entries"] if e.get("relevant_chunk_ids")]
    print(f"Ground truth: {len(labeled)} labeled entries (with chunk IDs).")

    # ── Get chunk IDs currently in DB ──────────────────────────────────────────
    from backend.db.models import PolicyChunk
    session = SessionLocal()
    try:
        chunk_ids_in_db: set[int] = {
            row[0] for row in session.query(PolicyChunk.id).all()
        }
    finally:
        session.close()
    print(f"DB contains {len(chunk_ids_in_db)} chunks.")

    # ── Evaluate each query ────────────────────────────────────────────────────
    per_query: list[dict] = []
    n_skipped = 0
    print(f"\nRunning retrieval for {len(labeled)} queries (MAX_K={MAX_K})...")

    session = SessionLocal()
    try:
        for i, entry in enumerate(labeled, start=1):
            if i % 10 == 0 or i == len(labeled):
                print(f"  [{i}/{len(labeled)}] {entry['query_id']} — {entry['category']}")

            result = _evaluate_query(session, entry, chunk_ids_in_db)
            if result is None:
                n_skipped += 1
                continue
            per_query.append(result)
    finally:
        session.close()

    if not per_query:
        raise RuntimeError(
            "All GT entries were skipped — chunk IDs in ground truth do not match DB. "
            "Re-generate the ground truth or re-ingest with the same DB."
        )

    print(f"\nEvaluated {len(per_query)} queries, skipped {n_skipped}.")

    # ── Aggregate ─────────────────────────────────────────────────────────────
    overall, per_category = _aggregate(per_query)

    # ── Assemble metrics dict ─────────────────────────────────────────────────
    from backend.config import settings
    metrics: dict = {
        "n_queries_evaluated": len(per_query),
        "n_queries_skipped": n_skipped,
        "K_values": K_VALUES,
        "overall": overall,
        "per_category": per_category,
        "config_snapshot": {
            "POLICY_TOP_K": settings.POLICY_TOP_K,
            "POLICY_TOP_N": settings.POLICY_TOP_N,
            "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
            "MAX_K_evaluated": MAX_K,
        },
        "per_query": per_query,
    }

    # ── Save ──────────────────────────────────────────────────────────────────
    out_json = RESULTS_DIR / "retrieval_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved       → {out_json}")

    # ── Plots ─────────────────────────────────────────────────────────────────
    _make_charts(per_query, overall, per_category)

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_summary(overall, per_category, len(per_query), n_skipped)

    return metrics


if __name__ == "__main__":
    evaluate_retrieval()