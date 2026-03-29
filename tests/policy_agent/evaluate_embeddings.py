"""
Test for Stage 2 — Embedding / Vector Space Quality

Loads PolicyChunk embeddings directly from the database (no re-embedding required)
and measures how well the embedding model structures the policy vector space.

Metrics:
    1. Intra-category cohesion     — avg pairwise cosine sim within each category
    2. Inter-category separation   — avg pairwise cosine sim across each category pair
    3. Hard-constraint separability — cluster gap: intra-HC sim minus cross-group sim
    4. Anisotropy score            — avg pairwise cosine sim across all embeddings
    5. Query-document alignment    — sim(query, relevant) − sim(query, non-relevant) [opt]

Visualisations:
    embedding_clusters.png  — 2-panel 2D scatter (PCA default, UMAP optional)
    embedding_heatmap.png   — N×N category similarity matrix + cohesion bar chart
    embedding_alignment.png — per-category alignment gap box plots [if --with-query-alignment]

Output:
    tests/policy_agent/results/embedding_metrics.json
    tests/policy_agent/results/embedding_clusters.png
    tests/policy_agent/results/embedding_heatmap.png

Usage:
    uv run python tests/policy_agent/evaluate_embeddings.py
    uv run python tests/policy_agent/evaluate_embeddings.py --with-query-alignment
    uv run python tests/policy_agent/evaluate_embeddings.py --use-umap

Prerequisites:
    1. PostgreSQL + pgvector running
    2. Policies ingested with embeddings (uv run python backend/db/ingest_policies.py)
    3. Eval dependencies installed (uv sync --extra eval)
    4. Ground truth dataset present (tests/policy_agent/test_cases/ground_truth_dataset.json)  [only required with --with-query-alignment]
    5. OPENAI_API_KEY set in .env  [only required with --with-query-alignment]
"""

import argparse
import json
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PolicyChunk

# ── Paths ─────────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_chunk_data() -> pd.DataFrame:
    """Query all PolicyChunk rows and return a DataFrame with numpy embeddings."""
    session = SessionLocal()
    try:
        chunks: list[PolicyChunk] = (
            session.query(PolicyChunk).order_by(PolicyChunk.id).all()
        )
    finally:
        session.close()

    rows = []
    for c in chunks:
        rows.append({
            "id": c.id,
            "source_file": c.source_file,
            "category": c.category or "unknown",
            "hard_constraint": bool(c.hard_constraint),
            "chunk_text": c.chunk_text,
            "embedding": np.array(c.embedding, dtype=np.float32),
        })
    return pd.DataFrame(rows)


def _pairwise_mean(a: np.ndarray, b: np.ndarray | None = None) -> float:
    """
    Avg cosine similarity within group a (upper triangle, no diagonal),
    or cross-group between a and b. Returns nan for groups too small to compare.
    """
    if b is None:
        if len(a) < 2:
            return float("nan")
        sim = cosine_similarity(a)
        upper = sim[np.triu_indices(len(a), k=1)]
        return float(np.mean(upper))
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    return float(cosine_similarity(a, b).mean())


def _r(v: float, n: int = 4) -> float | None:
    """Round a float to n decimal places; return None for nan/inf."""
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ─── Query-document alignment ─────────────────────────────────────────────────

def _compute_query_alignment(df: pd.DataFrame, emb_matrix: np.ndarray) -> dict:
    """Embed GT queries and compute cosine sim to relevant vs non-relevant chunks."""
    if not GT_PATH.exists():
        return {"computed": False, "error": f"GT file not found: {GT_PATH}"}

    with open(GT_PATH) as f:
        gt_data = json.load(f)

    labeled = [e for e in gt_data["entries"] if e.get("relevant_chunk_ids")]
    if not labeled:
        return {"computed": False, "error": "No labeled entries with chunk IDs in GT dataset"}

    print(f"  Embedding {len(labeled)} GT queries via OpenAI API...")
    from langchain_openai import OpenAIEmbeddings

    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    q_embs = np.array(
        embedder.embed_documents([e["query"] for e in labeled]),
        dtype=np.float32,
    )
    print("  Done.")

    chunk_id_set = set(df["id"].tolist())
    per_query = []
    for i, entry in enumerate(labeled):
        rel_ids = [cid for cid in entry["relevant_chunk_ids"] if cid in chunk_id_set]
        if not rel_ids:
            continue

        rel_mask = df["id"].isin(set(rel_ids)).values
        q_emb = q_embs[i : i + 1]
        rel_sim = float(cosine_similarity(q_emb, emb_matrix[rel_mask]).mean())
        non_rel_sim = (
            float(cosine_similarity(q_emb, emb_matrix[~rel_mask]).mean())
            if (~rel_mask).any()
            else 0.0
        )
        per_query.append({
            "query_id": entry["query_id"],
            "category": entry["category"],
            "relevant_sim": _r(rel_sim),
            "non_relevant_sim": _r(non_rel_sim),
            "alignment_gap": _r(rel_sim - non_rel_sim),
        })

    scores = pd.DataFrame(per_query)
    return {
        "computed": True,
        "n_queries_evaluated": len(per_query),
        "mean_relevant_sim": _r(float(scores["relevant_sim"].mean())),
        "mean_non_relevant_sim": _r(float(scores["non_relevant_sim"].mean())),
        "mean_alignment_gap": _r(float(scores["alignment_gap"].mean())),
        "per_category": {
            cat: {
                "n": len(grp),
                "mean_relevant_sim": _r(float(grp["relevant_sim"].mean())),
                "mean_alignment_gap": _r(float(grp["alignment_gap"].mean())),
            }
            for cat, grp in scores.groupby("category")
        },
        "per_query": per_query,
    }


# ─── 2D projection ────────────────────────────────────────────────────────────

def _project_2d(emb_matrix: np.ndarray, use_umap: bool) -> tuple[np.ndarray, str]:
    if use_umap:
        try:
            import umap as umap_lib
            print("  Running UMAP (n_neighbors=15, min_dist=0.1)...")
            proj = umap_lib.UMAP(
                n_components=2, random_state=42, n_neighbors=15, min_dist=0.1
            ).fit_transform(emb_matrix)
            return proj, "UMAP"
        except ImportError:
            print("  umap-learn not available, falling back to PCA.")

    print("  Running PCA...")
    pca = PCA(n_components=2, random_state=42)
    proj = pca.fit_transform(emb_matrix)
    evr = pca.explained_variance_ratio_
    return proj, f"PCA (PC1={evr[0]:.1%}, PC2={evr[1]:.1%})"


# ─── Plotting ─────────────────────────────────────────────────────────────────

def _make_cluster_plot(
    df: pd.DataFrame,
    proj: np.ndarray,
    proj_method: str,
    qd: dict,
) -> None:
    sns.set_theme(style="whitegrid")
    ncols = 3 if qd.get("computed") else 2
    fig, axes = plt.subplots(1, ncols, figsize=(8 * ncols, 7))

    categories = sorted(df["category"].unique().tolist())
    palette = sns.color_palette("tab10", len(categories))
    cat_color = {cat: palette[i] for i, cat in enumerate(categories)}
    hc = df["hard_constraint"].values.astype(bool)

    # Panel 1 — scatter by category (circles = soft, stars = hard-constraint)
    ax = axes[0]
    for cat in categories:
        mask_cat = (df["category"] == cat).values
        soft = mask_cat & ~hc
        hard = mask_cat & hc
        if soft.any():
            ax.scatter(proj[soft, 0], proj[soft, 1],
                       c=[cat_color[cat]], alpha=0.70, s=55, marker="o")
        if hard.any():
            ax.scatter(proj[hard, 0], proj[hard, 1],
                       c=[cat_color[cat]], alpha=0.95, s=130, marker="*",
                       edgecolors="black", linewidths=0.5)

    legend_handles = [
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=cat_color[cat], markersize=9, label=cat)
        for cat in categories
    ] + [
        Line2D([0], [0], marker="*", color="w", markerfacecolor="gray",
               markersize=13, markeredgecolor="black", label="hard_constraint"),
    ]
    ax.legend(handles=legend_handles, fontsize=8)
    ax.set_title(f"Policy Chunk Embeddings — {proj_method}\n(by category, ★ = hard_constraint)")
    ax.set_xlabel("Component 1")
    ax.set_ylabel("Component 2")

    # Panel 2 — scatter by hard_constraint only
    ax = axes[1]
    colors = np.where(hc, "firebrick", "steelblue")
    ax.scatter(proj[:, 0], proj[:, 1], c=colors, alpha=0.75, s=55)
    ax.legend(handles=[
        mpatches.Patch(color="steelblue", label="soft"),
        mpatches.Patch(color="firebrick", label="hard_constraint=True"),
    ], fontsize=9)
    ax.set_title(f"Hard-Constraint Separability — {proj_method}")
    ax.set_xlabel("Component 1")
    ax.set_ylabel("Component 2")

    # Panel 3 (optional) — query-document alignment gap by category
    if qd.get("computed") and qd.get("per_query"):
        ax = axes[2]
        per_q = pd.DataFrame(qd["per_query"])
        order = (
            per_q.groupby("category")["alignment_gap"]
            .mean()
            .sort_values(ascending=False)
            .index
        )
        sns.boxplot(data=per_q, x="category", y="alignment_gap",
                    order=order, ax=ax, palette="muted")
        ax.axhline(0, color="red", linestyle="--", linewidth=1, alpha=0.6)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
        ax.set_title("Query-Document Alignment Gap\n(sim_relevant − sim_non_relevant)")
        ax.set_ylabel("Cosine similarity gap")
        ax.set_xlabel("")

    fig.suptitle(
        f"Stage 2 — Embedding Quality  |  model={settings.EMBEDDING_MODEL}  |  "
        f"n={len(df)} chunks",
        fontsize=11, y=1.01,
    )
    plt.tight_layout()
    out = RESULTS_DIR / "embedding_clusters.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Cluster plot saved  → {out}")


def _make_heatmap(sim_df: pd.DataFrame, metrics: dict) -> None:
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Left — N×N similarity matrix
    ax = axes[0]
    sns.heatmap(
        sim_df.astype(float),
        annot=True, fmt=".3f",
        cmap="RdYlGn", vmin=0.0, vmax=1.0,
        linewidths=0.5, ax=ax,
        cbar_kws={"label": "Avg Pairwise Cosine Similarity"},
    )
    ax.set_title(
        "Category Similarity Matrix\n"
        "(diagonal = intra-cohesion, off-diagonal = inter-separation)"
    )
    ax.tick_params(axis="x", rotation=30)
    ax.tick_params(axis="y", rotation=0)

    # Right — cohesion bar chart with global anisotropy baseline
    ax = axes[1]
    cats = list(metrics["intra_category_cohesion"].keys())
    vals = [v or 0.0 for v in metrics["intra_category_cohesion"].values()]
    x = np.arange(len(cats))
    bars = ax.bar(x, vals, color="steelblue", alpha=0.8)
    global_aniso = metrics["anisotropy"]["avg_pairwise_cosine_sim"] or 0.0
    ax.axhline(global_aniso, color="red", linestyle="--",
               label=f"Global baseline (anisotropy) = {global_aniso:.3f}")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Avg pairwise cosine similarity")
    ax.set_title("Intra-Category Cohesion vs Global Anisotropy Baseline")
    ax.legend(fontsize=9)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    out = RESULTS_DIR / "embedding_heatmap.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Heatmap saved       → {out}")


# ─── Summary printing ─────────────────────────────────────────────────────────

def _print_summary(metrics: dict) -> None:
    SEP = "=" * 64
    print(f"\n{SEP}")
    print("  STAGE 2 — EMBEDDING / VECTOR SPACE QUALITY SUMMARY")
    print(SEP)
    print(f"  Total chunks:    {metrics['total_chunks']}")
    print(f"  Embedding model: {metrics['embedding_model']} ({metrics['embedding_dims']} dims)")
    print()

    print("  Intra-category cohesion:")
    for cat, val in metrics["intra_category_cohesion"].items():
        bar = "#" * int((val or 0) * 40)
        print(f"    {cat:<22}  {str(val):>7}  {bar}")
    print()

    inter = metrics["inter_category_separation"]
    pairs = [
        (c1, c2, v)
        for c1, row in inter.items()
        for c2, v in row.items()
        if c1 < c2 and v is not None
    ]
    if pairs:
        pairs_sorted = sorted(pairs, key=lambda x: x[2])
        print("  Inter-category separation:")
        print(f"    Most separated:   {pairs_sorted[0][0]} <-> {pairs_sorted[0][1]}"
              f"  sim={pairs_sorted[0][2]:.4f}")
        print(f"    Least separated:  {pairs_sorted[-1][0]} <-> {pairs_sorted[-1][1]}"
              f"  sim={pairs_sorted[-1][2]:.4f}")
        avg_inter = float(np.mean([p[2] for p in pairs]))
        avg_intra = float(np.nanmean([v for v in metrics["intra_category_cohesion"].values()
                                      if v is not None]))
        print(f"    Gap (intra−inter): {avg_intra - avg_inter:.4f}")
    print()

    hc = metrics["hard_constraint_separability"]
    print(f"  Hard-constraint separability:")
    print(f"    HC chunks={hc['n_hard_constraint_chunks']}  "
          f"intra-HC sim={hc['intra_sim_hard_constraint']}  "
          f"cross sim={hc['cross_sim_hc_vs_non_hc']}  "
          f"gap={hc['separation_gap']}")
    print()

    aniso = metrics["anisotropy"]
    print(f"  Anisotropy:  avg_pairwise={aniso['avg_pairwise_cosine_sim']}  "
          f"centroid_sim={aniso['avg_cosine_sim_to_centroid']}  "
          f"(n_sampled={aniso['sample_size']})")
    print()

    qd = metrics["query_document_alignment"]
    if qd.get("computed"):
        print(f"  Query-document alignment  (n={qd['n_queries_evaluated']} queries):")
        print(f"    Mean sim to relevant:     {qd['mean_relevant_sim']}")
        print(f"    Mean sim to non-relevant: {qd['mean_non_relevant_sim']}")
        print(f"    Mean alignment gap:       {qd['mean_alignment_gap']}")
    else:
        print("  Query-document alignment: not computed  (re-run with --with-query-alignment)")
    print()

    _print_performance_summary(metrics)
    print(SEP)


def _print_performance_summary(metrics: dict) -> None:
    print("  Performance Summary:")

    # Per-category cohesion
    for cat, val in metrics["intra_category_cohesion"].items():
        if val is not None and val < 0.40:
            print(f"  [WARN] '{cat}' cohesion={val:.3f} — chunks are semantically scattered "
                  "within this category; consider splitting its source PDF more finely.")

    # Intra/inter gap
    inter = metrics["inter_category_separation"]
    all_inter = [v for row in inter.values() for v in row.values() if v is not None]
    if all_inter:
        avg_inter = float(np.mean(all_inter))
        avg_intra = float(np.nanmean([v for v in metrics["intra_category_cohesion"].values()
                                      if v is not None]))
        gap = avg_intra - avg_inter
        if gap < 0.05:
            print(f"  [WARN] Intra/inter gap={gap:.3f} — embedding model barely separates "
                  "policy domains. Consider text-embedding-3-large or bge-m3.")
        else:
            print(f"  [OK]   Intra/inter gap={gap:.3f} — embedding model distinguishes domains.")

    # Hard-constraint separability
    hc_gap = metrics["hard_constraint_separability"].get("separation_gap")
    if hc_gap is not None:
        if hc_gap > 0.03:
            print(f"  [OK]   Hard-constraint separation gap={hc_gap:.3f} — "
                  "HC chunks form a distinguishable cluster.")
        else:
            print(f"  [WARN] Hard-constraint gap={hc_gap:.3f} — HC chunks don't cluster "
                  "distinctly; the embedding model treats hard/soft constraints similarly.")

    # Anisotropy
    aniso_val = metrics["anisotropy"]["avg_pairwise_cosine_sim"] or 0.0
    if aniso_val > 0.90:
        print(f"  [WARN] High anisotropy ({aniso_val:.3f}) — embeddings occupy a narrow cone; "
              "space may be degenerate. Try a different model or mean-centering.")
    elif aniso_val > 0.70:
        print(f"  [INFO] Moderate anisotropy ({aniso_val:.3f}) — typical for domain-specific text.")
    else:
        print(f"  [OK]   Anisotropy={aniso_val:.3f} — well-distributed embedding space.")

    # Query-document alignment
    qd = metrics["query_document_alignment"]
    if qd.get("computed"):
        gap = qd.get("mean_alignment_gap") or 0.0
        if gap < 0.05:
            print(f"  [WARN] Low alignment gap={gap:.3f} — queries are not significantly closer "
                  "to their relevant chunks. Consider HyDE or finer chunk granularity.")
        else:
            print(f"  [OK]   Alignment gap={gap:.3f} — queries land near their relevant chunks.")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def evaluate_embeddings(
    with_query_alignment: bool = False,
    use_umap: bool = False,
) -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)

    # ── Load ──────────────────────────────────────────────────────────────────
    print("Loading embeddings from DB...")
    df = _load_chunk_data()
    if df.empty:
        raise RuntimeError(
            "No PolicyChunk rows found. Run: uv run python backend/db/ingest_policies.py"
        )
    emb_matrix = np.vstack(df["embedding"].values)   # (N, D)
    print(f"Loaded {len(df)} chunks  ({emb_matrix.shape[1]}-dim embeddings).")
    categories = sorted(df["category"].unique().tolist())

    # ── 1. Intra-category cohesion ────────────────────────────────────────────
    print("Computing intra-category cohesion...")
    cohesion: dict[str, float | None] = {
        cat: _r(_pairwise_mean(emb_matrix[(df["category"] == cat).values]))
        for cat in categories
    }

    # ── 2. Inter-category separation ─────────────────────────────────────────
    print("Computing inter-category separation...")
    separation: dict[str, dict[str, float | None]] = {c: {} for c in categories}
    for c1, c2 in combinations(categories, 2):
        val = _r(_pairwise_mean(
            emb_matrix[(df["category"] == c1).values],
            emb_matrix[(df["category"] == c2).values],
        ))
        separation[c1][c2] = val
        separation[c2][c1] = val

    # Full similarity matrix for heatmap (diagonal = cohesion)
    sim_df = pd.DataFrame(np.nan, index=categories, columns=categories, dtype=float)
    for cat in categories:
        sim_df.loc[cat, cat] = cohesion[cat]
    for c1, c2 in combinations(categories, 2):
        sim_df.loc[c1, c2] = separation[c1][c2]
        sim_df.loc[c2, c1] = separation[c1][c2]

    # ── 3. Hard-constraint separability ──────────────────────────────────────
    print("Computing hard-constraint separability...")
    hc_mask = df["hard_constraint"].values.astype(bool)
    hc_emb, non_hc_emb = emb_matrix[hc_mask], emb_matrix[~hc_mask]
    hc_intra = _pairwise_mean(hc_emb)
    non_hc_intra = _pairwise_mean(non_hc_emb)
    hc_cross = _pairwise_mean(hc_emb, non_hc_emb)
    sep_gap = (
        _r(hc_intra - hc_cross)
        if not (np.isnan(hc_intra) or np.isnan(hc_cross))
        else None
    )

    # ── 4. Anisotropy ─────────────────────────────────────────────────────────
    print("Computing anisotropy...")
    n = len(emb_matrix)
    rng = np.random.default_rng(42)
    sample_size = min(n, 300)
    sample = emb_matrix[rng.choice(n, size=sample_size, replace=False)]
    upper = cosine_similarity(sample)[np.triu_indices(sample_size, k=1)]
    centroid = emb_matrix.mean(axis=0, keepdims=True)
    centroid_sims = cosine_similarity(emb_matrix, centroid).flatten()

    # ── 5. Query-document alignment (optional) ────────────────────────────────
    qd_alignment: dict = {"computed": False}
    if with_query_alignment:
        print("Computing query-document alignment...")
        qd_alignment = _compute_query_alignment(df, emb_matrix)

    # ── 6. 2D projection ──────────────────────────────────────────────────────
    print("Computing 2D projection for scatter plot...")
    proj, proj_method = _project_2d(emb_matrix, use_umap)

    # ── Assemble ──────────────────────────────────────────────────────────────
    metrics: dict = {
        "total_chunks": len(df),
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dims": int(emb_matrix.shape[1]),
        "categories": categories,
        "intra_category_cohesion": cohesion,
        "inter_category_separation": separation,
        "hard_constraint_separability": {
            "n_hard_constraint_chunks": int(hc_mask.sum()),
            "n_non_hard_constraint_chunks": int((~hc_mask).sum()),
            "intra_sim_hard_constraint": _r(hc_intra),
            "intra_sim_non_hard_constraint": _r(non_hc_intra),
            "cross_sim_hc_vs_non_hc": _r(hc_cross),
            "separation_gap": sep_gap,
        },
        "anisotropy": {
            "avg_pairwise_cosine_sim": _r(float(np.mean(upper))),
            "avg_cosine_sim_to_centroid": _r(float(np.mean(centroid_sims))),
            "sample_size": sample_size,
            "note": (
                "Lower avg_pairwise_cosine_sim indicates a more isotropic "
                "(better-distributed) embedding space."
            ),
        },
        "query_document_alignment": qd_alignment,
        "config_snapshot": {
            "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
            "POLICY_CHUNK_SIZE": settings.POLICY_CHUNK_SIZE,
            "POLICY_CHUNK_OVERLAP": settings.POLICY_CHUNK_OVERLAP,
        },
    }

    # ── Save ──────────────────────────────────────────────────────────────────
    out_json = RESULTS_DIR / "embedding_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved       → {out_json}")

    # ── Plots ──────────────────────────────────────────────────────────────────
    _make_cluster_plot(df, proj, proj_method, qd_alignment)
    _make_heatmap(sim_df, metrics)

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_summary(metrics)

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 2: Embedding / Vector Space Quality Evaluation"
    )
    parser.add_argument(
        "--with-query-alignment",
        action="store_true",
        help=(
            "Embed GT queries via the OpenAI API and compute per-query "
            "sim(relevant) − sim(non-relevant) alignment gaps."
        ),
    )
    parser.add_argument(
        "--use-umap",
        action="store_true",
        help="Use UMAP for 2D projection (falls back to PCA if umap-learn is unavailable).",
    )
    args = parser.parse_args()
    evaluate_embeddings(
        with_query_alignment=args.with_query_alignment,
        use_umap=args.use_umap,
    )
