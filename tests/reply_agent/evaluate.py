"""
Reply Agent — Structured Output Consistency & Correctness Benchmark

Evaluates the accuracy and stability of the reply agent's self-assessment fields:

    confidence_level       — "high" | "medium" | "low"
    unverified_claims      — list of hedged statements (presence/absence tested)
    tone_flags             — list of anomaly labels

Each GT case specifies:
    expected_confidence_level      — the correct confidence for the given state
    expected_has_unverified_claims — True if unverified_claims should be non-empty
    expected_tone_flags            — exact set of tone labels expected

Each case is run n_runs times (default 7 — higher than risk node because
the reply agent uses temperature=0.3) to measure stability.

Core metrics per case:
    confidence_accuracy   — % runs where confidence_level == expected
    unverified_accuracy   — % runs where (len(unverified_claims) > 0) == expected
    tone_accuracy         — % runs where set(tone_flags) == expected set (exact)
    consistency_rate      — % runs matching modal confidence_level
    flip_count            — runs deviating from modal confidence_level

Keyword guards (where defined in the GT case):
    keyword_include_rate  — % runs where all must_include keywords appear in reply_text
    keyword_exclude_rate  — % runs where no must_exclude keywords appear in reply_text

Aggregated across cases:
    mean_confidence_accuracy   — primary LLM accuracy signal
    mean_unverified_accuracy   — secondary accuracy signal (data gap detection)
    mean_tone_accuracy         — tertiary accuracy signal
    mean_consistency_rate      — overall stability signal
    flip_rate                  — % cases with at least one inconsistent run

Output:
    tests/reply_agent/results/reply_agent_metrics.json
    tests/reply_agent/results/reply_agent_charts.png

Usage:
    uv run python tests/reply_agent/evaluate.py

Prerequisites:
    1. Ground truth at tests/reply_agent/test_cases/ground_truth_dataset.json
       (generate with: uv run python tests/reply_agent/generate_ground_truth.py)
    2. LLM API key set in .env
"""

import json
import time
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from backend.agents.reply_agent import reply_agent

# ── Paths ──────────────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# Pass / warn thresholds
THRESHOLDS = {
    "confidence_accuracy": {"ok": 0.85, "warn": 0.70},
    "unverified_accuracy": {"ok": 0.90, "warn": 0.75},
    "tone_accuracy":       {"ok": 0.80, "warn": 0.65},
    "consistency_rate":    {"ok": 0.90, "warn": 0.75},
    "flip_rate":           {"ok": 0.20, "warn": 0.40},   # lower is better
    "keyword_rate":        {"ok": 1.00, "warn": 0.85},   # keyword guards
}


def _r(v, n: int = 4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ── State consistency pre-check ────────────────────────────────────────────────

def _precheck_state(entry: dict) -> str | None:
    """Return an error string if the state is structurally invalid, else None."""
    state = entry.get("state", {})
    required = ["sender_role", "sender_name", "intent_label", "urgency_level",
                "raw_message", "soul_context", "rules_context"]
    missing = [f for f in required if not state.get(f)]
    if missing:
        return f"Missing required state fields: {missing}"
    exp_conf = entry.get("expected_confidence_level")
    if exp_conf not in {"high", "medium", "low"}:
        return f"Invalid expected_confidence_level: '{exp_conf}'"
    return None


# ── Per-case evaluation ────────────────────────────────────────────────────────

def _base_fields(entry: dict) -> dict:
    return {
        "case_id": entry["case_id"],
        "scenario": entry["scenario"],
        "boundary_type": entry["boundary_type"],
        "expected_confidence_level": entry["expected_confidence_level"],
        "expected_has_unverified_claims": entry["expected_has_unverified_claims"],
        "expected_tone_flags": entry.get("expected_tone_flags", []),
        "is_boundary_case": entry.get("is_boundary_case", False),
        "n_runs": entry.get("n_runs", 7),
        "keyword_must_include": entry.get("keyword_must_include", []),
        "keyword_must_exclude": entry.get("keyword_must_exclude", []),
    }


def _check_keywords(
    reply_text: str,
    must_include: list[str],
    must_exclude: list[str],
) -> tuple[bool, bool]:
    """Return (include_pass, exclude_pass) for a single reply_text."""
    include_pass = all(kw.lower() in reply_text.lower() for kw in must_include) if must_include else True
    exclude_pass = all(kw.lower() not in reply_text.lower() for kw in must_exclude) if must_exclude else True
    return include_pass, exclude_pass


def _evaluate_case(entry: dict) -> dict:
    """Run reply_agent n_runs times for one GT entry; compute consistency metrics."""
    state = entry["state"]
    n_runs = entry.get("n_runs", 7)
    expected_confidence = entry["expected_confidence_level"]
    expected_has_unverified = entry["expected_has_unverified_claims"]
    expected_tone = frozenset(entry.get("expected_tone_flags", []))
    must_include = entry.get("keyword_must_include", [])
    must_exclude = entry.get("keyword_must_exclude", [])
    case_id = entry["case_id"]

    base = _base_fields(entry)

    # Pre-check
    pre_err = _precheck_state(entry)
    if pre_err:
        return {
            **base,
            "error": f"State validation failed: {pre_err}",
            "n_valid_runs": 0,
            "confidence_levels_observed": [],
            "confidence_counts": {},
            "modal_confidence": None,
            "consistency_rate": None,
            "confidence_accuracy": None,
            "unverified_accuracy": None,
            "tone_accuracy": None,
            "keyword_include_rate": None,
            "keyword_exclude_rate": None,
            "flip_count": 0,
            "mean_latency_ms": None,
        }

    # Run reply_agent N times
    runs: list[dict] = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        try:
            result = reply_agent(dict(state))  # shallow copy avoids state mutation
            latency_ms = _r((time.perf_counter() - t0) * 1000, 1)
            conf = (result.get("confidence_level") or "").lower().strip()
            if conf not in {"high", "medium", "low"}:
                conf = "unknown"
            unverified = result.get("unverified_claims") or []
            tone = frozenset(
                (f or "").lower().strip()
                for f in (result.get("tone_flags") or [])
                if f
            )
            reply_text = result.get("reply_text") or ""
            inc_pass, exc_pass = _check_keywords(reply_text, must_include, must_exclude)
            runs.append({
                "confidence_level": conf,
                "has_unverified": len(unverified) > 0,
                "tone_flags": tone,
                "keyword_include_pass": inc_pass,
                "keyword_exclude_pass": exc_pass,
                "reply_text": reply_text,
                "latency_ms": latency_ms,
                "error": None,
            })
        except Exception as exc:
            latency_ms = _r((time.perf_counter() - t0) * 1000, 1)
            runs.append({
                "confidence_level": None,
                "has_unverified": None,
                "tone_flags": None,
                "keyword_include_pass": None,
                "keyword_exclude_pass": None,
                "reply_text": "",
                "latency_ms": latency_ms,
                "error": str(exc),
            })

    valid_runs = [r for r in runs if r["error"] is None]
    n_valid = len(valid_runs)

    if n_valid == 0:
        errors = [r["error"] for r in runs]
        return {
            **base,
            "error": f"All {n_runs} runs failed. First error: {errors[0]}",
            "n_valid_runs": 0,
            "confidence_levels_observed": [],
            "confidence_counts": {},
            "modal_confidence": None,
            "consistency_rate": None,
            "confidence_accuracy": None,
            "unverified_accuracy": None,
            "tone_accuracy": None,
            "keyword_include_rate": None,
            "keyword_exclude_rate": None,
            "flip_count": 0,
            "mean_latency_ms": None,
        }

    # ── Confidence metrics ────────────────────────────────────────────────────
    conf_levels = [r["confidence_level"] for r in valid_runs]
    conf_counts = Counter(conf_levels)
    modal_confidence = conf_counts.most_common(1)[0][0]

    consistency_rate = _r(conf_counts[modal_confidence] / n_valid)
    confidence_accuracy = _r(conf_counts.get(expected_confidence, 0) / n_valid)
    flip_count = n_valid - conf_counts[modal_confidence]

    # ── Unverified claims accuracy ────────────────────────────────────────────
    unverified_accuracy = _r(
        sum(1 for r in valid_runs if r["has_unverified"] == expected_has_unverified) / n_valid
    )

    # ── Tone flag accuracy ────────────────────────────────────────────────────
    # Exact set match: the agent's tone_flags must equal expected exactly.
    # For "clean" cases (expected=[]), any flag is a false positive.
    # For diagnostic cases (expected=[speculative]), exact match is required.
    tone_accuracy = _r(
        sum(1 for r in valid_runs if r["tone_flags"] == expected_tone) / n_valid
    )

    # ── Keyword guard rates ───────────────────────────────────────────────────
    keyword_include_rate = (
        _r(sum(1 for r in valid_runs if r["keyword_include_pass"]) / n_valid)
        if must_include else None
    )
    keyword_exclude_rate = (
        _r(sum(1 for r in valid_runs if r["keyword_exclude_pass"]) / n_valid)
        if must_exclude else None
    )

    mean_latency = _r(
        sum(r["latency_ms"] for r in valid_runs) / n_valid, 1
    ) if valid_runs else None

    return {
        **base,
        "error": None,
        "n_valid_runs": n_valid,
        "confidence_levels_observed": conf_levels,
        "confidence_counts": dict(conf_counts),
        "modal_confidence": modal_confidence,
        "consistency_rate": consistency_rate,
        "confidence_accuracy": confidence_accuracy,
        "unverified_accuracy": unverified_accuracy,
        "tone_accuracy": tone_accuracy,
        "keyword_include_rate": keyword_include_rate,
        "keyword_exclude_rate": keyword_exclude_rate,
        "flip_count": flip_count,
        "mean_latency_ms": mean_latency,
    }


# ── Aggregation ────────────────────────────────────────────────────────────────

def _aggregate(per_case: list[dict]) -> dict:
    df = pd.DataFrame(per_case)
    valid = df[df["error"].isna()].copy()

    def safe_mean(series) -> float | None:
        s = series.dropna()
        return _r(float(s.mean())) if len(s) else None

    # Overall aggregation
    overall = {
        "n_total": len(df),
        "n_valid": len(valid),
        "n_errors": int(df["error"].notna().sum()),
        "n_boundary_cases": int(valid["is_boundary_case"].sum()) if len(valid) else 0,
        "mean_confidence_accuracy": safe_mean(valid["confidence_accuracy"]),
        "mean_unverified_accuracy": safe_mean(valid["unverified_accuracy"]),
        "mean_tone_accuracy": safe_mean(valid["tone_accuracy"]),
        "mean_consistency_rate": safe_mean(valid["consistency_rate"]),
        "flip_rate": _r(float((valid["flip_count"] > 0).mean())) if len(valid) else None,
        "total_flip_count": int(valid["flip_count"].sum()) if len(valid) else 0,
        "mean_latency_ms": safe_mean(valid["mean_latency_ms"]),
        "p95_latency_ms": (
            _r(float(valid["mean_latency_ms"].dropna().quantile(0.95)), 1)
            if valid["mean_latency_ms"].notna().any() else None
        ),
    }

    # Keyword guard summary (only cases that defined guards)
    kw_inc = valid["keyword_include_rate"].dropna()
    kw_exc = valid["keyword_exclude_rate"].dropna()
    overall["keyword_include_rate"] = _r(float(kw_inc.mean())) if len(kw_inc) else None
    overall["keyword_exclude_rate"] = _r(float(kw_exc.mean())) if len(kw_exc) else None

    # Per expected confidence level breakdown
    by_level: dict = {}
    if len(valid):
        for lvl, grp in valid.groupby("expected_confidence_level"):
            by_level[str(lvl)] = {
                "n": len(grp),
                "mean_confidence_accuracy": safe_mean(grp["confidence_accuracy"]),
                "mean_unverified_accuracy": safe_mean(grp["unverified_accuracy"]),
                "mean_tone_accuracy": safe_mean(grp["tone_accuracy"]),
                "mean_consistency_rate": safe_mean(grp["consistency_rate"]),
                "flip_rate": _r(float((grp["flip_count"] > 0).mean())) if len(grp) else None,
            }

    # Per boundary_type breakdown
    by_boundary: dict = {}
    if len(valid):
        for bt, grp in valid.groupby("boundary_type"):
            by_boundary[str(bt)] = {
                "n": len(grp),
                "mean_confidence_accuracy": safe_mean(grp["confidence_accuracy"]),
                "mean_consistency_rate": safe_mean(grp["consistency_rate"]),
                "flip_rate": _r(float((grp["flip_count"] > 0).mean())) if len(grp) else None,
            }

    # Observed confidence distribution per expected group
    conf_distribution: dict = {}
    for lvl in ["high", "medium", "low"]:
        dist = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        subset = valid[valid["expected_confidence_level"] == lvl] if len(valid) else pd.DataFrame()
        for _, row in subset.iterrows():
            for obs in (row.get("confidence_levels_observed") or []):
                if obs in dist:
                    dist[obs] += 1
        conf_distribution[lvl] = dist

    # Worst cases by confidence_accuracy
    worst: list[dict] = []
    if len(valid):
        worst = (
            valid.nsmallest(5, "confidence_accuracy")
            [[
                "case_id", "boundary_type", "expected_confidence_level",
                "modal_confidence", "confidence_accuracy", "unverified_accuracy",
                "tone_accuracy", "consistency_rate", "flip_count",
            ]]
            .to_dict(orient="records")
        )

    return {
        "overall": overall,
        "by_expected_level": by_level,
        "by_boundary_type": by_boundary,
        "conf_distribution": conf_distribution,
        "worst_cases": worst,
    }


# ── Charts ─────────────────────────────────────────────────────────────────────

def _make_charts(per_case: list[dict], aggregated: dict) -> None:
    sns.set_theme(style="whitegrid", palette="muted")
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    axes = axes.flatten()

    df = pd.DataFrame(per_case)
    valid = df[df["error"].isna()].copy()
    by_level = aggregated["by_expected_level"]
    overall = aggregated["overall"]

    def _bar_color(v, metric, lower=False):
        t = THRESHOLDS[metric]
        ok, warn = t["ok"], t["warn"]
        if lower:
            return "mediumseagreen" if v <= ok else "goldenrod" if v <= warn else "coral"
        return "mediumseagreen" if v >= ok else "goldenrod" if v >= warn else "coral"

    # ── Panel 1: Confidence accuracy by expected level ────────────────────────
    ax = axes[0]
    levels_order = [l for l in ["high", "medium", "low"] if l in by_level]
    conf_acc_vals = [by_level[l]["mean_confidence_accuracy"] or 0 for l in levels_order]
    colors = [_bar_color(v, "confidence_accuracy") for v in conf_acc_vals]
    bars = ax.bar(levels_order, [v * 100 for v in conf_acc_vals], color=colors, alpha=0.85)
    ax.axhline(THRESHOLDS["confidence_accuracy"]["ok"] * 100, color="green",
               linestyle="--", linewidth=1,
               label=f"OK ≥ {THRESHOLDS['confidence_accuracy']['ok']*100:.0f}%")
    ax.axhline(THRESHOLDS["confidence_accuracy"]["warn"] * 100, color="orange",
               linestyle=":", linewidth=1,
               label=f"Warn ≥ {THRESHOLDS['confidence_accuracy']['warn']*100:.0f}%")
    ax.set_ylim(0, 115)
    ax.set_ylabel("Confidence Accuracy (%)")
    ax.set_title("Confidence Level Accuracy by Expected Level\n(% of runs matching expected_confidence_level)")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, conf_acc_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{val*100:.1f}%", ha="center", va="bottom", fontsize=10)

    # ── Panel 2: Unverified & tone accuracy per case (grouped bar) ───────────
    ax = axes[1]
    if len(valid):
        case_ids = valid["case_id"].tolist()
        unverified_accs = [v * 100 if v is not None else 0
                           for v in valid["unverified_accuracy"].tolist()]
        tone_accs = [v * 100 if v is not None else 0
                     for v in valid["tone_accuracy"].tolist()]
        x = np.arange(len(case_ids))
        w = 0.38
        ax.bar(x - w / 2, unverified_accs, w, label="Unverified accuracy",
               color="steelblue", alpha=0.82)
        ax.bar(x + w / 2, tone_accs, w, label="Tone accuracy",
               color="mediumpurple", alpha=0.82)
        ax.axhline(THRESHOLDS["unverified_accuracy"]["ok"] * 100,
                   color="steelblue", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.axhline(THRESHOLDS["tone_accuracy"]["ok"] * 100,
                   color="mediumpurple", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(case_ids, rotation=45, ha="right", fontsize=7)
        ax.set_ylim(0, 115)
        ax.set_ylabel("Accuracy (%)")
        ax.set_title("Unverified Claims & Tone Flag Accuracy per Case")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center", transform=ax.transAxes)

    # ── Panel 3: Observed confidence distribution by expected group (stacked) ─
    ax = axes[2]
    conf_dist = aggregated["conf_distribution"]
    groups = [g for g in ["high", "medium", "low"] if g in conf_dist]
    h_counts = [conf_dist[g].get("high", 0) for g in groups]
    m_counts = [conf_dist[g].get("medium", 0) for g in groups]
    l_counts = [conf_dist[g].get("low", 0) for g in groups]
    x = np.arange(len(groups))
    bar_w = 0.5
    ax.bar(x, h_counts, bar_w, label="Observed: high", color="mediumseagreen", alpha=0.85)
    ax.bar(x, m_counts, bar_w, bottom=h_counts, label="Observed: medium", color="goldenrod", alpha=0.85)
    ax.bar(x, l_counts, bar_w,
           bottom=[h + m for h, m in zip(h_counts, m_counts)],
           label="Observed: low", color="coral", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Expected:\n{g}" for g in groups])
    ax.set_ylabel("Total run count across group")
    ax.set_title("Observed Confidence by Expected Group\n(ideal: matching colour dominates each bar)")
    ax.legend(fontsize=8)
    totals = [h + m + l for h, m, l in zip(h_counts, m_counts, l_counts)]
    for xi, tot in zip(x, totals):
        if tot > 0:
            ax.text(xi, tot + 0.4, f"n={tot}", ha="center", va="bottom", fontsize=9)

    # ── Panel 4: Consistency rate histogram ───────────────────────────────────
    ax = axes[3]
    if len(valid) and valid["consistency_rate"].notna().any():
        rates = valid["consistency_rate"].dropna() * 100
        bins = [0, 20, 40, 60, 80, 90, 100, 101]
        counts, edges = np.histogram(rates, bins=bins)
        bar_labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–90%", "90–100%", "100%"]
        bar_colors = [
            "coral" if edge_r <= 60 else "goldenrod" if edge_r <= 90 else "mediumseagreen"
            for edge_r in edges[1:]
        ]
        ax.bar(range(len(counts)), counts, color=bar_colors, alpha=0.85, width=0.7)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(bar_labels, fontsize=8)
        ax.set_ylabel("Number of Cases")
        ax.set_title("Consistency Rate Distribution\n(% of n_runs matching modal confidence_level)")
        from matplotlib.patches import Patch
        ax.legend(handles=[
            Patch(facecolor="coral", alpha=0.85, label="< 60% (unstable)"),
            Patch(facecolor="goldenrod", alpha=0.85, label="60–90% (borderline)"),
            Patch(facecolor="mediumseagreen", alpha=0.85, label="≥ 90% (stable)"),
        ], fontsize=8)
        for i, cnt in enumerate(counts):
            if cnt > 0:
                ax.text(i, cnt + 0.05, str(cnt), ha="center", va="bottom", fontsize=9)
    else:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center", transform=ax.transAxes)

    # ── Panel 5: Mean latency by scenario group ───────────────────────────────
    ax = axes[4]

    def _group(bt: str) -> str:
        if bt.startswith("full") or bt.startswith("policy_approved") or bt.startswith("all_claims") or bt == "clean_factual_reply":
            return "high confidence"
        if bt.startswith("partial") or bt.startswith("policy_requires") or bt.startswith("delivery") or bt.startswith("supplier"):
            return "medium confidence"
        if bt.startswith("no_sub") or bt.startswith("price_not") or bt.startswith("complaint"):
            return "low confidence"
        return "boundary / role"

    if len(valid):
        valid_lat = valid.copy()
        valid_lat["group"] = valid_lat["boundary_type"].apply(_group)
        grp_lat = valid_lat.groupby("group")["mean_latency_ms"].mean()
        group_order = [g for g in [
            "high confidence", "medium confidence", "low confidence", "boundary / role"
        ] if g in grp_lat.index]
        lat_vals = [grp_lat.get(g, 0) for g in group_order]
        bars_l = ax.bar(group_order, lat_vals, color="mediumpurple", alpha=0.85)
        ax.set_xticklabels(group_order, fontsize=8, rotation=10)
        ax.set_ylabel("Mean Latency (ms)")
        ax.set_title("Mean Reply Agent Latency\nby Scenario Group")
        for bar, val in zip(bars_l, lat_vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                    f"{val:.0f} ms", ha="center", va="bottom", fontsize=9)
    else:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")

    # ── Panel 6: Overall scorecard table ──────────────────────────────────────
    ax = axes[5]
    ax.axis("off")

    def _fmt_pct(v):
        return f"{v*100:.1f}%" if v is not None else "n/a"

    def _tag(v, metric, lower=False):
        if v is None:
            return ""
        ok, warn = THRESHOLDS[metric]["ok"], THRESHOLDS[metric]["warn"]
        if lower:
            return "[OK]" if v <= ok else "[WARN]" if v <= warn else "[FAIL]"
        return "[OK]" if v >= ok else "[WARN]" if v >= warn else "[FAIL]"

    kw_inc = overall.get("keyword_include_rate")
    kw_exc = overall.get("keyword_exclude_rate")

    scorecard = [
        ("Mean confidence accuracy",
         f"{_fmt_pct(overall['mean_confidence_accuracy'])}  {_tag(overall['mean_confidence_accuracy'], 'confidence_accuracy')}"),
        ("Mean unverified accuracy",
         f"{_fmt_pct(overall['mean_unverified_accuracy'])}  {_tag(overall['mean_unverified_accuracy'], 'unverified_accuracy')}"),
        ("Mean tone accuracy",
         f"{_fmt_pct(overall['mean_tone_accuracy'])}  {_tag(overall['mean_tone_accuracy'], 'tone_accuracy')}"),
        ("Mean consistency rate",
         f"{_fmt_pct(overall['mean_consistency_rate'])}  {_tag(overall['mean_consistency_rate'], 'consistency_rate')}"),
        ("Flip rate (any run differs)",
         f"{_fmt_pct(overall['flip_rate'])}  {_tag(overall['flip_rate'], 'flip_rate', lower=True)}"),
        ("Total flip count",         str(overall["total_flip_count"])),
        ("Keyword include rate",
         f"{_fmt_pct(kw_inc)}  {_tag(kw_inc, 'keyword_rate')}" if kw_inc is not None else "n/a  (no guards defined)"),
        ("Keyword exclude rate",
         f"{_fmt_pct(kw_exc)}  {_tag(kw_exc, 'keyword_rate')}" if kw_exc is not None else "n/a  (no guards defined)"),
        ("Mean latency",             f"{overall['mean_latency_ms']} ms"),
        ("P95 latency",              f"{overall['p95_latency_ms']} ms"),
        ("Cases evaluated",          str(overall["n_valid"])),
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

    fig.suptitle(
        "Reply Agent — Structured Output Consistency & Correctness Benchmark",
        fontsize=12, y=1.01,
    )
    plt.tight_layout()
    out = RESULTS_DIR / "reply_agent_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved → {out}")


# ── Summary printing ───────────────────────────────────────────────────────────

def _print_summary(aggregated: dict) -> None:
    SEP = "=" * 66
    overall = aggregated["overall"]
    by_level = aggregated["by_expected_level"]

    print(f"\n{SEP}")
    print("REPLY AGENT — STRUCTURED OUTPUT BENCHMARK SUMMARY")
    print(SEP)
    print(
        f"  Cases evaluated:       {overall['n_valid']}  "
        f"({overall['n_errors']} errors  |  {overall['n_boundary_cases']} boundary)"
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

    print("  Overall metrics:")
    print(f"    Mean confidence accuracy:  {_fmt(overall['mean_confidence_accuracy'], 'confidence_accuracy')}")
    print(f"    Mean unverified accuracy:  {_fmt(overall['mean_unverified_accuracy'], 'unverified_accuracy')}")
    print(f"    Mean tone accuracy:        {_fmt(overall['mean_tone_accuracy'], 'tone_accuracy')}")
    print(f"    Mean consistency rate:     {_fmt(overall['mean_consistency_rate'], 'consistency_rate')}")
    print(f"    Flip rate (≥1 flip):       {_fmt(overall['flip_rate'], 'flip_rate', lower=True)}")
    print(f"    Total flip count:          {overall['total_flip_count']}")

    kw_inc = overall.get("keyword_include_rate")
    kw_exc = overall.get("keyword_exclude_rate")
    if kw_inc is not None:
        print(f"    Keyword include rate:      {_fmt(kw_inc, 'keyword_rate')}")
    if kw_exc is not None:
        print(f"    Keyword exclude rate:      {_fmt(kw_exc, 'keyword_rate')}")

    print(f"    Mean latency:              {overall['mean_latency_ms']} ms")
    print(f"    P95 latency:               {overall['p95_latency_ms']} ms")
    print()

    print("  Per expected confidence level breakdown:")
    header = (
        f"  {'Confidence':<12}{'N':>4}  "
        f"{'ConfAcc':>10}  {'UnverAcc':>10}  {'ToneAcc':>10}  {'FlipRate':>10}"
    )
    print(header)
    print("  " + "-" * 62)
    for lvl in ["high", "medium", "low"]:
        if lvl not in by_level:
            continue
        ld = by_level[lvl]
        print(
            f"  {lvl:<12}{ld['n']:>4}  "
            f"{_fmt(ld['mean_confidence_accuracy']):>10}  "
            f"{_fmt(ld['mean_unverified_accuracy']):>10}  "
            f"{_fmt(ld['mean_tone_accuracy']):>10}  "
            f"{_fmt(ld['flip_rate'], 'flip_rate', lower=True):>10}"
        )
    print()

    worst = aggregated.get("worst_cases", [])
    if worst:
        print("  Lowest confidence-accuracy cases:")
        for w in worst:
            ca = f"{w['confidence_accuracy']*100:.0f}%" if w["confidence_accuracy"] is not None else "n/a"
            print(
                f"    [{w['case_id']}] {w['boundary_type']}"
                f"  expected={w['expected_confidence_level']}"
                f"  modal={w['modal_confidence']}"
                f"  conf_acc={ca}"
            )
        print()

    print(SEP)


def _print_recommendations(aggregated: dict) -> None:
    overall = aggregated["overall"]
    ca = overall.get("mean_confidence_accuracy") or 0
    ua = overall.get("mean_unverified_accuracy") or 0
    ta = overall.get("mean_tone_accuracy") or 0
    cons = overall.get("mean_consistency_rate") or 0
    flip = overall.get("flip_rate") or 0
    kw_inc = overall.get("keyword_include_rate")
    kw_exc = overall.get("keyword_exclude_rate")

    print("\n  Recommendations:")

    if ca < THRESHOLDS["confidence_accuracy"]["warn"]:
        print(
            "  [FAIL] Confidence accuracy low — the agent frequently self-assesses at the "
            "wrong confidence level. Review the prompt definitions for 'high', 'medium', "
            "and 'low' in reply_agent.py. Add clearer criteria tied to completed_tasks coverage."
        )
    elif ca < THRESHOLDS["confidence_accuracy"]["ok"]:
        print(
            "  [WARN] Confidence accuracy borderline — inspect worst_cases in metrics JSON. "
            "Medium/low boundary cases are the most likely source of drift."
        )

    if ua < THRESHOLDS["unverified_accuracy"]["warn"]:
        print(
            "  [FAIL] Unverified claims accuracy low — agent is not reliably detecting data gaps. "
            "Strengthen the unverified_claims field description in the ReplyOutput schema "
            "to be more explicit about when claims must be listed."
        )
    elif ua < THRESHOLDS["unverified_accuracy"]["ok"]:
        print(
            "  [WARN] Unverified claims accuracy borderline — some cases produce false "
            "positives (unnecessary claims) or false negatives (missing claims). "
            "Review cases where retriever data is partial but delivery is implied."
        )

    if ta < THRESHOLDS["tone_accuracy"]["warn"]:
        print(
            "  [FAIL] Tone accuracy low — agent is either over-flagging clean responses "
            "or missing expected flags. Review tone_flags definitions in ReplyOutput schema. "
            "Consider adding examples of each label to the field description."
        )
    elif ta < THRESHOLDS["tone_accuracy"]["ok"]:
        print(
            "  [WARN] Tone accuracy borderline — check which cases are producing unexpected "
            "flags. Over-flagging 'speculative' in clean replies is the most common failure."
        )

    if cons < THRESHOLDS["consistency_rate"]["warn"]:
        print(
            "  [FAIL] Consistency rate low — agent output is highly variable across runs. "
            "Temperature=0.3 is intentional but high variance suggests boundary cases are "
            "genuinely ambiguous. Consider whether expected labels are too strict."
        )
    elif cons < THRESHOLDS["consistency_rate"]["ok"]:
        print(
            "  [WARN] Consistency rate borderline — review boundary cases (ra-011, ra-014) "
            "and consider loosening their expected outputs to 'medium OR low' patterns."
        )

    if flip > THRESHOLDS["flip_rate"]["warn"]:
        print(
            "  [FAIL] Flip rate high — more than 40% of cases have at least one inconsistent run. "
            "Consider whether temperature=0.3 is too high for this evaluation task. "
            "A dedicated lower-temperature structured-output mode may be appropriate."
        )
    elif flip > THRESHOLDS["flip_rate"]["ok"]:
        print("  [WARN] Flip rate elevated — monitor across repeated evaluation runs.")

    if kw_inc is not None and kw_inc < THRESHOLDS["keyword_rate"]["warn"]:
        print(
            "  [FAIL] Keyword include guard failing — owner cases are not including required "
            "internal data (margin %, revenue) in the reply. Check that owner tone posture "
            "in reply_agent.py does not suppress internal data disclosure."
        )

    if kw_exc is not None and kw_exc < THRESHOLDS["keyword_rate"]["warn"]:
        print(
            "  [FAIL] Keyword exclude guard failing — internal data (margins, cost prices) "
            "is leaking into non-owner replies. CRITICAL: check RULE.md injection and "
            "the confidentiality instructions in the reply prompt."
        )

    all_ok = (
        ca >= THRESHOLDS["confidence_accuracy"]["ok"]
        and ua >= THRESHOLDS["unverified_accuracy"]["ok"]
        and ta >= THRESHOLDS["tone_accuracy"]["ok"]
        and cons >= THRESHOLDS["consistency_rate"]["ok"]
        and (kw_inc is None or kw_inc >= THRESHOLDS["keyword_rate"]["ok"])
        and (kw_exc is None or kw_exc >= THRESHOLDS["keyword_rate"]["ok"])
    )
    if all_ok:
        print("  [OK] Reply agent self-assessment is stable and accurate. No critical issues.")

    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def evaluate_reply_agent() -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)

    if not GT_PATH.exists():
        raise FileNotFoundError(
            f"Ground truth not found: {GT_PATH}\n"
            "Generate it first:\n"
            "  uv run python tests/reply_agent/generate_ground_truth.py"
        )

    with open(GT_PATH, encoding="utf-8") as f:
        gt_data = json.load(f)
    entries = gt_data["entries"]
    total_runs = sum(e.get("n_runs", 7) for e in entries)
    print(
        f"Ground truth: {len(entries)} cases  |  "
        f"{total_runs} total LLM calls  (reply agent at temp=0.3)"
    )
    print("Each run invokes reply_agent() once and captures confidence_level, "
          "unverified_claims presence, and tone_flags.\n")

    per_case: list[dict] = []
    for i, entry in enumerate(entries, start=1):
        n = entry.get("n_runs", 7)
        bt = entry["boundary_type"]
        exp_conf = entry["expected_confidence_level"]
        exp_unver = entry["expected_has_unverified_claims"]
        exp_tone = entry.get("expected_tone_flags", [])
        bmark = "  [BOUNDARY]" if entry.get("is_boundary_case") else ""
        print(
            f"  [{i:>2}/{len(entries)}] {entry['case_id']}  {bt}"
            f"  expected_conf={exp_conf}  unver={exp_unver}  tone={exp_tone}"
            f"  n_runs={n}{bmark}"
        )
        result = _evaluate_case(entry)
        if result.get("error"):
            print(f"         ERROR: {result['error']}")
        else:
            ca = result["confidence_accuracy"]
            ua = result["unverified_accuracy"]
            ta = result["tone_accuracy"]
            cons = result["consistency_rate"]
            print(
                f"         modal_conf={result['modal_confidence']}"
                f"  conf_acc={ca*100:.0f}%"
                f"  unver_acc={ua*100:.0f}%"
                f"  tone_acc={ta*100:.0f}%"
                f"  consist={cons*100:.0f}%"
                f"  flips={result['flip_count']}/{n}"
            )
        per_case.append(result)

    print(f"\nCompleted {len(per_case)} cases.\n")

    aggregated = _aggregate(per_case)

    metrics = {
        "n_cases": len(per_case),
        "aggregated": aggregated,
        "per_case": per_case,
    }

    out_json = RESULTS_DIR / "reply_agent_metrics.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"Metrics saved → {out_json}")

    try:
        _make_charts(per_case, aggregated)
    except Exception as exc:
        print(f"[WARN] Chart generation failed: {exc}")

    _print_summary(aggregated)
    _print_recommendations(aggregated)

    return metrics


if __name__ == "__main__":
    evaluate_reply_agent()
