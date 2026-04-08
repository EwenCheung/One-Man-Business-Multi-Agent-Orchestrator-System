"""
Test for Stage 1 — Chunking Quality Evaluation

Loads every PolicyChunk row from the database and computes six metrics that
quantify how well the MarkdownTextSplitter + config parameters are performing:

    1. Chunk size distribution   — char/token count stats (mean, std, percentiles)
    2. Boundary integrity rate   — % of chunks that end at a sentence boundary
    3. Orphan sentence rate      — % of chunks that start with a partial sentence
    4. Semantic coherence score  — avg consecutive-sentence cosine similarity [opt]
    5. Overlap fidelity          — % of adjacent-chunk overlaps that are coherent text
    6. Coverage completeness     — % of GT queries with ≥1 relevant chunk in DB

Output:
    tests/policy_agent/results/chunking_metrics.json
    tests/policy_agent/results/chunking_histograms.png

Usage:
    uv run python tests/policy_agent/evaluate_chunking.py
    uv run python tests/policy_agent/evaluate_chunking.py --with-embeddings

Prerequisites:
    1. Connection to Supabase established
    2. Policies ingested (uv run python backend/db/ingest_policies.py)
    3. Eval dependencies installed (uv sync --extra eval)
    4. Ground truth dataset present (tests/policy_agent/test_cases/ground_truth_dataset.json)  [for coverage completeness metric]
    5. OPENAI_API_KEY set in .env  [only required with --with-embeddings]
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
import nltk
import numpy as np
import pandas as pd
import seaborn as sns
import tiktoken
from scipy.stats import skew, kurtosis
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PolicyChunk

# ── NLTK data ────────────────────────────────────────────────────────────────
nltk.download("punkt_tab", quiet=True)
nltk.download("punkt", quiet=True)

# ── Paths ────────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# ── Regex helpers ─────────────────────────────────────────────────────────────
_SENTENCE_END = re.compile(r'[.!?]["\']?\s*$')
_HEADING = re.compile(r'^#{1,6}\s')
_BULLET = re.compile(r'^[-*•]\s')
_NUMBERED = re.compile(r'^\d+[.)]\s')


# ─── Metric helpers ───────────────────────────────────────────────────────────

def _ends_at_boundary(text: str) -> bool:
    """True if the chunk ends at a sentence or markdown structural boundary."""
    stripped = text.rstrip()
    if _SENTENCE_END.search(stripped):
        return True
    last_line = stripped.splitlines()[-1].strip() if stripped else ""
    return bool(
        _HEADING.match(last_line)
        or _BULLET.match(last_line)
        or _NUMBERED.match(last_line)
    )


def _starts_orphan(text: str) -> bool:
    """True if the chunk starts with a continuation (lowercase, no structural marker).

    A lowercase-starting chunk almost certainly means the splitter cut a sentence
    and the fragment continues from the previous chunk — i.e., an orphan start.
    """
    stripped = text.lstrip()
    if not stripped:
        return False
    if (
        _HEADING.match(stripped)
        or _BULLET.match(stripped)
        or _NUMBERED.match(stripped)
        or stripped.startswith("**")   # markdown bold opening
        or stripped.startswith("*")    # markdown italic opening
    ):
        return False
    return stripped[0].islower()


def _find_overlap(text1: str, text2: str, min_len: int = 15) -> str | None:
    """Return the longest suffix of text1 that is a prefix of text2 (>= min_len chars)."""
    max_check = min(len(text1), len(text2), 500)
    for length in range(max_check, min_len - 1, -1):
        if text1[-length:] == text2[:length]:
            return text2[:length]
    return None


def _overlap_coherent(text: str) -> bool:
    """True if the overlap text contains at least one complete sentence."""
    if len(text.strip()) < 15:
        return False
    sentences = nltk.sent_tokenize(text)
    return any(_SENTENCE_END.search(s.rstrip()) for s in sentences)


def _dist_stats(series: pd.Series) -> dict:
    """Return a full distribution stat dict for a numeric series."""
    return {
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": float(series.min()),
        "max": float(series.max()),
        "p5": float(series.quantile(0.05)),
        "p25": float(series.quantile(0.25)),
        "p50": float(series.quantile(0.50)),
        "p75": float(series.quantile(0.75)),
        "p95": float(series.quantile(0.95)),
        "skewness": float(skew(series)),
        "kurtosis": float(kurtosis(series)),
    }


# ─── Main evaluation ──────────────────────────────────────────────────────────

def evaluate_chunking(with_embeddings: bool = False) -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)
    enc = tiktoken.get_encoding("cl100k_base")  # matches text-embedding-3-small tokenizer

    # ── 1. Load all chunks from DB ────────────────────────────────────────────
    session = SessionLocal()
    try:
        chunks: list[PolicyChunk] = (
            session.query(PolicyChunk)
            .order_by(PolicyChunk.source_file, PolicyChunk.page_number, PolicyChunk.chunk_index)
            .all()
        )
    finally:
        session.close()

    if not chunks:
        raise RuntimeError(
            "No PolicyChunk rows found. Run: uv run python backend/db/ingest_policies.py"
        )

    print(f"Loaded {len(chunks)} chunks from DB.")

    # ── 2. Per-chunk metrics ──────────────────────────────────────────────────
    print("Computing per-chunk metrics...")
    rows = []
    for c in chunks:
        text = c.chunk_text
        sentences = nltk.sent_tokenize(text)
        rows.append({
            "id": c.id,
            "source_file": c.source_file,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "category": c.category or "unknown",
            "hard_constraint": bool(c.hard_constraint),
            "char_len": len(text),
            "token_len": len(enc.encode(text)),
            "n_sentences": len(sentences),
            "ends_at_boundary": _ends_at_boundary(text),
            "starts_orphan": _starts_orphan(text),
            "_text": text,
            "_sentences": sentences,
        })

    df = pd.DataFrame(rows)

    # ── 3. Overlap fidelity ───────────────────────────────────────────────────
    print("Computing overlap fidelity between adjacent chunks...")
    overlap_records = []
    for (src, pg), group in df.groupby(["source_file", "page_number"]):
        ordered = group.sort_values("chunk_index")["_text"].tolist()
        for i in range(len(ordered) - 1):
            overlap = _find_overlap(ordered[i], ordered[i + 1])
            overlap_records.append({
                "source_file": src,
                "page_number": pg,
                "has_overlap": overlap is not None,
                "overlap_len": len(overlap) if overlap else 0,
                "overlap_coherent": _overlap_coherent(overlap) if overlap else False,
            })

    ov_df = pd.DataFrame(
        overlap_records if overlap_records
        else [{"source_file": "", "page_number": 0,
               "has_overlap": False, "overlap_len": 0, "overlap_coherent": False}]
    )

    # ── 4. Semantic coherence (optional, requires OpenAI API) ─────────────────
    coherence_scores: list[float] = []
    if with_embeddings:
        print("Computing semantic coherence (OpenAI embeddings API)...")
        from langchain_openai import OpenAIEmbeddings

        embedder = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
        multi_sentence = df[df["n_sentences"] >= 2]
        print(f"  Evaluating {len(multi_sentence)} multi-sentence chunks...")
        for _, row in multi_sentence.iterrows():
            sents = row["_sentences"]
            vecs = np.array(embedder.embed_documents(sents))
            sims = [
                float(cosine_similarity(vecs[i : i + 1], vecs[i + 1 : i + 2])[0][0])
                for i in range(len(vecs) - 1)
            ]
            coherence_scores.append(float(np.mean(sims)))
        print(f"  Done ({len(coherence_scores)} scores computed).")

    # ── 5. Coverage completeness ──────────────────────────────────────────────
    print("Computing coverage completeness from ground truth...")
    if not GT_PATH.exists():
        print(f"  [WARN] Ground truth not found at {GT_PATH} — skipping coverage check.")
        coverage = {"gt_entries_with_chunk_ids": 0, "entries_covered": 0, "coverage_pct": None}
    else:
        with open(GT_PATH) as f:
            gt = json.load(f)
        chunk_ids_in_db: set[str] = {str(cid) for cid in df["id"].tolist()}
        labeled = [e for e in gt["entries"] if e.get("relevant_chunk_ids")]
        covered = sum(
            1 for e in labeled if any(str(cid) in chunk_ids_in_db for cid in e["relevant_chunk_ids"])
        )
        coverage = {
            "gt_entries_with_chunk_ids": len(labeled),
            "entries_covered": covered,
            "coverage_pct": round(covered / len(labeled) * 100, 2) if labeled else None,
            "note": (
                "chunk IDs in ground truth are fixed at generation time — "
                "re-ingest with --force will invalidate them"
            ),
        }

    # ── 6. Aggregate into metrics dict ────────────────────────────────────────
    metrics: dict = {
        "total_chunks": len(df),
        "chunk_size_distribution": {
            "chars": _dist_stats(df["char_len"]),
            "tokens": _dist_stats(df["token_len"]),
        },
        "boundary_integrity_rate_pct": round(float(df["ends_at_boundary"].mean() * 100), 2),
        "orphan_sentence_rate_pct": round(float(df["starts_orphan"].mean() * 100), 2),
        "sentences_per_chunk": _dist_stats(df["n_sentences"].astype(float)),
        "overlap_fidelity": {
            "total_adjacent_pairs": len(overlap_records),
            "pairs_with_overlap": int(ov_df["has_overlap"].sum()),
            "overlap_detection_rate_pct": round(float(ov_df["has_overlap"].mean() * 100), 2),
            "coherent_overlap_rate_pct": round(
                float(
                    ov_df.loc[ov_df["has_overlap"], "overlap_coherent"].mean() * 100
                    if ov_df["has_overlap"].any()
                    else 0.0
                ),
                2,
            ),
            "mean_overlap_len_chars": round(
                float(ov_df.loc[ov_df["has_overlap"], "overlap_len"].mean())
                if ov_df["has_overlap"].any()
                else 0.0,
                2,
            ),
        },
        "semantic_coherence": {
            "computed": with_embeddings,
            "n_chunks_evaluated": len(coherence_scores),
            "mean": round(float(np.mean(coherence_scores)), 4) if coherence_scores else None,
            "std": round(float(np.std(coherence_scores)), 4) if coherence_scores else None,
            "min": round(float(np.min(coherence_scores)), 4) if coherence_scores else None,
            "max": round(float(np.max(coherence_scores)), 4) if coherence_scores else None,
        },
        "coverage_completeness": coverage,
        "per_category": {
            cat: {
                "n_chunks": len(grp),
                "char_len": _dist_stats(grp["char_len"]),
                "token_len_mean": round(float(grp["token_len"].mean()), 1),
                "boundary_integrity_rate_pct": round(float(grp["ends_at_boundary"].mean() * 100), 2),
                "orphan_rate_pct": round(float(grp["starts_orphan"].mean() * 100), 2),
                "mean_sentences_per_chunk": round(float(grp["n_sentences"].mean()), 2),
            }
            for cat, grp in df.groupby("category")
        },
        "config_snapshot": {
            "POLICY_CHUNK_SIZE": settings.POLICY_CHUNK_SIZE,
            "POLICY_CHUNK_OVERLAP": settings.POLICY_CHUNK_OVERLAP,
            "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
            "splitter": "MarkdownTextSplitter",
        },
    }

    # ── 7. Save JSON ──────────────────────────────────────────────────────────
    out_json = RESULTS_DIR / "chunking_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved → {out_json}")

    # ── 8. Generate plots ─────────────────────────────────────────────────────
    _make_plots(df, ov_df, coherence_scores)

    # ── 9. Print summary + tuning hints ──────────────────────────────────────
    _print_summary(metrics)

    return metrics


# ─── Plotting ─────────────────────────────────────────────────────────────────

def _make_plots(
    df: pd.DataFrame,
    ov_df: pd.DataFrame,
    coherence_scores: list[float],
) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    # 1 — Character length distribution
    ax = axes[0]
    sns.histplot(df["char_len"], bins=30, ax=ax, color="steelblue")
    ax.axvline(df["char_len"].mean(), color="red", linestyle="--",
               label=f"mean={df['char_len'].mean():.0f}")
    ax.axvline(df["char_len"].quantile(0.05), color="orange", linestyle=":",
               label="P5 / P95")
    ax.axvline(df["char_len"].quantile(0.95), color="orange", linestyle=":")
    ax.set_title("Chunk Character Length Distribution")
    ax.set_xlabel("Characters")
    ax.legend(fontsize=8)

    # 2 — Token length distribution
    ax = axes[1]
    sns.histplot(df["token_len"], bins=30, ax=ax, color="mediumseagreen")
    ax.axvline(df["token_len"].mean(), color="red", linestyle="--",
               label=f"mean={df['token_len'].mean():.0f}")
    ax.axvline(512, color="purple", linestyle="--", alpha=0.6, label="512-token limit")
    ax.set_title("Chunk Token Length Distribution")
    ax.set_xlabel("Tokens (cl100k_base)")
    ax.legend(fontsize=8)

    # 3 — Boundary integrity & orphan rate by category
    ax = axes[2]
    cat_df = (
        df.groupby("category")
        .agg(boundary=("ends_at_boundary", "mean"), orphan=("starts_orphan", "mean"))
        .reset_index()
    )
    x = np.arange(len(cat_df))
    w = 0.35
    ax.bar(x - w / 2, cat_df["boundary"] * 100, w, label="Boundary integrity %",
           color="steelblue")
    ax.bar(x + w / 2, cat_df["orphan"] * 100, w, label="Orphan start %",
           color="salmon")
    ax.set_xticks(x)
    ax.set_xticklabels(cat_df["category"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Percentage (%)")
    ax.set_title("Boundary Integrity & Orphan Rate by Category")
    ax.legend(fontsize=8)

    # 4 — Chunk size distribution by category (box plot)
    ax = axes[3]
    categories = df["category"].unique().tolist()
    data_by_cat = [df.loc[df["category"] == cat, "char_len"].tolist() for cat in categories]
    bp = ax.boxplot(data_by_cat, labels=categories, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("lightsteelblue")
    ax.set_xticklabels(categories, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Characters")
    ax.set_title("Chunk Size Distribution by Category")

    # 5 — Sentences per chunk histogram
    ax = axes[4]
    sns.histplot(df["n_sentences"], bins=range(1, df["n_sentences"].max() + 2),
                 ax=ax, color="mediumpurple", discrete=True)
    ax.axvline(df["n_sentences"].mean(), color="red", linestyle="--",
               label=f"mean={df['n_sentences'].mean():.1f}")
    ax.set_title("Sentences per Chunk")
    ax.set_xlabel("Sentence count (NLTK)")
    ax.legend(fontsize=8)

    # 6 — Semantic coherence (if computed) OR overlap fidelity breakdown
    ax = axes[5]
    if coherence_scores:
        sns.histplot(coherence_scores, bins=20, ax=ax, color="goldenrod")
        ax.axvline(float(np.mean(coherence_scores)), color="red", linestyle="--",
                   label=f"mean={np.mean(coherence_scores):.3f}")
        ax.set_title("Intra-Chunk Semantic Coherence")
        ax.set_xlabel("Avg consecutive-sentence cosine similarity")
        ax.legend(fontsize=8)
    else:
        if ov_df["has_overlap"].any():
            no_ov = int((~ov_df["has_overlap"]).sum())
            incoherent = int((ov_df["has_overlap"] & ~ov_df["overlap_coherent"]).sum())
            coherent = int((ov_df["has_overlap"] & ov_df["overlap_coherent"]).sum())
            ax.bar(
                ["No overlap detected", "Incoherent overlap", "Coherent overlap"],
                [no_ov, incoherent, coherent],
                color=["#d62728", "#ff7f0e", "#2ca02c"],
            )
            ax.set_ylabel("Adjacent chunk pairs")
            ax.set_title("Overlap Fidelity (Adjacent Pairs)")
        else:
            ax.text(0.5, 0.5, "No adjacent pairs found",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_title("Overlap Fidelity")

    fig.suptitle(
        f"Stage 1 — Chunking Quality  |  "
        f"chunk_size={settings.POLICY_CHUNK_SIZE}  overlap={settings.POLICY_CHUNK_OVERLAP}  "
        f"splitter=MarkdownTextSplitter",
        fontsize=11,
        y=1.01,
    )
    plt.tight_layout()
    out_png = RESULTS_DIR / "chunking_histograms.png"
    plt.savefig(str(out_png), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Plots saved  → {out_png}")


# ─── Summary printing ─────────────────────────────────────────────────────────

def _print_summary(metrics: dict) -> None:
    SEP = "=" * 62
    print(f"\n{SEP}")
    print("  STAGE 1 — CHUNKING QUALITY SUMMARY")
    print(SEP)

    print(f"  Total chunks:           {metrics['total_chunks']}")
    cfg = metrics["config_snapshot"]
    print(
        f"  Config:                 chunk_size={cfg['POLICY_CHUNK_SIZE']}  "
        f"overlap={cfg['POLICY_CHUNK_OVERLAP']}  "
        f"splitter={cfg['splitter']}"
    )
    print()

    c = metrics["chunk_size_distribution"]["chars"]
    t = metrics["chunk_size_distribution"]["tokens"]
    print(f"  Chunk size (chars)      mean={c['mean']:.0f}  std={c['std']:.0f}"
          f"  range=[{c['min']:.0f}, {c['max']:.0f}]  p95={c['p95']:.0f}")
    print(f"  Chunk size (tokens)     mean={t['mean']:.0f}  std={t['std']:.0f}"
          f"  range=[{t['min']:.0f}, {t['max']:.0f}]  p95={t['p95']:.0f}")
    print()

    print(f"  Boundary integrity:     {metrics['boundary_integrity_rate_pct']:.1f}%")
    print(f"  Orphan sentence rate:   {metrics['orphan_sentence_rate_pct']:.1f}%")
    print()

    ov = metrics["overlap_fidelity"]
    print(f"  Adjacent pairs:         {ov['total_adjacent_pairs']}")
    print(f"  Overlap detected:       {ov['overlap_detection_rate_pct']:.1f}%"
          f"  (mean len {ov['mean_overlap_len_chars']:.0f} chars)")
    print(f"  Coherent overlap:       {ov['coherent_overlap_rate_pct']:.1f}%")
    print()

    sc = metrics["semantic_coherence"]
    if sc["computed"]:
        print(f"  Semantic coherence:     mean={sc['mean']:.3f}  std={sc['std']:.3f}"
              f"  [{sc['min']:.3f}, {sc['max']:.3f}]")
    else:
        print("  Semantic coherence:     not computed  (re-run with --with-embeddings)")
    print()

    cov = metrics["coverage_completeness"]
    if cov["coverage_pct"] is not None:
        print(f"  GT coverage:            {cov['coverage_pct']:.1f}%"
              f"  ({cov['entries_covered']}/{cov['gt_entries_with_chunk_ids']} labeled entries)")
    else:
        print("  GT coverage:            skipped (ground truth file not found)")
    print()

    print("  Per-category breakdown:")
    header = f"  {'Category':<22} {'N':>4}  {'Chars':>7}  {'Tokens':>6}  {'Boundary':>9}  {'Orphan':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for cat, cm in metrics["per_category"].items():
        print(
            f"  {cat:<22} {cm['n_chunks']:>4}  "
            f"{cm['char_len']['mean']:>7.0f}  "
            f"{cm['token_len_mean']:>6.0f}  "
            f"{cm['boundary_integrity_rate_pct']:>8.1f}%  "
            f"{cm['orphan_rate_pct']:>6.1f}%"
        )

    print()
    _print_performance_summary(metrics)
    print(SEP)


def _print_performance_summary(metrics: dict) -> None:
    print("  Performance Summary:")
    b_rate = metrics["boundary_integrity_rate_pct"]
    o_rate = metrics["orphan_sentence_rate_pct"]
    token_p95 = metrics["chunk_size_distribution"]["tokens"]["p95"]
    char_p95 = metrics["chunk_size_distribution"]["chars"]["p95"]
    ov = metrics["overlap_fidelity"]
    cov = metrics["coverage_completeness"]
    sc = metrics["semantic_coherence"]

    # Boundary integrity
    if b_rate >= 80:
        print(f"  [OK]   Boundary integrity {b_rate:.1f}% — splitter respects sentence ends well.")
    elif b_rate >= 60:
        print(f"  [WARN] Boundary integrity {b_rate:.1f}% — consider smaller POLICY_CHUNK_SIZE "
              "or RecursiveCharacterTextSplitter.")
    else:
        print(f"  [FAIL] Boundary integrity {b_rate:.1f}% — chunks frequently cut mid-sentence. "
              "Decrease POLICY_CHUNK_SIZE significantly or switch splitter.")

    # Orphan rate
    if o_rate <= 10:
        print(f"  [OK]   Orphan rate {o_rate:.1f}% — overlap is preserving context adequately.")
    elif o_rate <= 25:
        print(f"  [WARN] Orphan rate {o_rate:.1f}% — increase POLICY_CHUNK_OVERLAP to reduce "
              "mid-sentence starts.")
    else:
        print(f"  [FAIL] Orphan rate {o_rate:.1f}% — many chunks start mid-sentence. "
              "Significantly increase POLICY_CHUNK_OVERLAP.")

    # Token ceiling
    chunk_size = settings.POLICY_CHUNK_SIZE
    if token_p95 > 512:
        print(f"  [WARN] Token P95 ({token_p95:.0f}) exceeds 512 — some chunks may be truncated "
              "by the embedding model.")
    else:
        print(f"  [OK]   Token P95 {token_p95:.0f} — well within embedding model limits.")

    if char_p95 > chunk_size * 1.1:
        print(f"  [WARN] Char P95 ({char_p95:.0f}) exceeds chunk_size * 1.1 "
              f"({chunk_size * 1.1:.0f}) — splitter occasionally overshoots the target size.")

    # Overlap fidelity
    if ov["overlap_detection_rate_pct"] < 40:
        print(f"  [WARN] Low overlap detection ({ov['overlap_detection_rate_pct']:.1f}%) — "
              "POLICY_CHUNK_OVERLAP may not be taking effect; check splitter behaviour.")
    elif ov["coherent_overlap_rate_pct"] < 50:
        print(f"  [WARN] Overlap detected but only {ov['coherent_overlap_rate_pct']:.1f}% is "
              "coherent text — overlap is cutting mid-sentence; increase POLICY_CHUNK_OVERLAP.")
    else:
        print(f"  [OK]   Overlap fidelity {ov['coherent_overlap_rate_pct']:.1f}% coherent.")

    # Coverage completeness
    if cov["coverage_pct"] is not None:
        if cov["coverage_pct"] >= 95:
            print(f"  [OK]   GT coverage {cov['coverage_pct']:.1f}% — all expected chunks are in DB.")
        else:
            missing = cov["gt_entries_with_chunk_ids"] - cov["entries_covered"]
            print(f"  [WARN] GT coverage {cov['coverage_pct']:.1f}% — {missing} GT entries reference "
                  "chunk IDs not found in DB. The DB may have been re-ingested after GT generation.")

    # Semantic coherence
    if sc["computed"] and sc["mean"] is not None:
        if sc["mean"] >= 0.7:
            print(f"  [OK]   Semantic coherence mean={sc['mean']:.3f} — chunks are internally cohesive.")
        elif sc["mean"] >= 0.5:
            print(f"  [WARN] Semantic coherence mean={sc['mean']:.3f} — moderate cohesion; "
                  "consider a SemanticChunker for better boundary detection.")
        else:
            print(f"  [FAIL] Semantic coherence mean={sc['mean']:.3f} — chunks are semantically "
                  "scattered; switch to a semantic splitter.")
    print()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 1: Chunking Quality Evaluation for Policy Agent RAG pipeline."
    )
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help=(
            "Compute intra-chunk semantic coherence by embedding each sentence via "
            "the OpenAI API (adds latency and API cost — proportional to total chunk count)."
        ),
    )
    args = parser.parse_args()
    evaluate_chunking(with_embeddings=args.with_embeddings)
