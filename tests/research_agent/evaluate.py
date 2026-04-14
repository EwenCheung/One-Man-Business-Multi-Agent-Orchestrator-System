"""
Research Agent — Synthesis Consistency & Correctness Benchmark

Evaluates the accuracy and stability of the research agent's synthesis step:

    confidence        — "high" | "medium" | "low"
    caveat            — present or absent (correct detection of gaps/staleness)
    sources           — present or absent (correct source attribution)

Tavily is bypassed entirely. ``_synthesise`` is called directly with
pre-defined stubbed ``raw_results`` strings from the ground truth dataset,
isolating synthesis quality from external search availability.

Each case is run n_runs times (default 5 — lower than reply agent because
the research agent uses temperature=0.0, producing near-deterministic output).

Core metrics per case:
    confidence_accuracy     — % runs where confidence == expected
    caveat_accuracy         — % runs where (caveat is not None) == expected
    source_attribution_rate — % runs where (sources non-empty) == expected
    consistency_rate        — % runs matching modal confidence
    flip_count              — runs deviating from modal confidence

Keyword guards (where defined in the GT case):
    keyword_include_rate  — % runs where all must_include keywords appear in findings text
    keyword_exclude_rate  — % runs where no must_exclude keywords appear in findings text

Aggregated across cases:
    mean_confidence_accuracy      — primary LLM accuracy signal
    mean_caveat_accuracy          — data gap detection signal
    mean_source_attribution_rate  — source attribution signal
    mean_consistency_rate         — overall stability signal
    flip_rate                     — % cases with at least one inconsistent run

Output:
    tests/research_agent/results/research_agent_metrics.json
    tests/research_agent/results/research_agent_charts.png

Usage:
    uv run python tests/research_agent/evaluate.py
    uv run python tests/research_agent/evaluate.py --case rsch-001
    uv run python tests/research_agent/evaluate.py --n-runs 1

Prerequisites:
    1. Ground truth at tests/research_agent/test_cases/ground_truth_dataset.json
       (generate with: uv run python tests/research_agent/generate_ground_truth.py)
    2. LLM API key set in .env
"""

import argparse
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

from backend.agents.research_agent import _synthesise
from backend.utils.llm_provider import get_chat_llm

# ── Paths ──────────────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# Pass / warn thresholds
THRESHOLDS = {
    "confidence_accuracy":     {"ok": 0.90, "warn": 0.75},  # higher bar: temperature=0.0
    "caveat_accuracy":         {"ok": 0.90, "warn": 0.75},
    "source_attribution_rate": {"ok": 0.90, "warn": 0.75},
    "consistency_rate":        {"ok": 0.95, "warn": 0.80},
    "flip_rate":               {"ok": 0.10, "warn": 0.30},  # lower is better
    "keyword_rate":            {"ok": 1.00, "warn": 0.85},
}


def _r(v, n: int = 4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ── State consistency pre-check ────────────────────────────────────────────────

def _precheck_entry(entry: dict) -> str | None:
    """Return an error string if the entry is structurally invalid, else None."""
    if not entry.get("task_description", "").strip():
        return "task_description is missing or empty"
    if not entry.get("raw_results", "").strip():
        return "raw_results is missing or empty"
    exp_conf = entry.get("expected_confidence")
    if exp_conf not in {"high", "medium", "low"}:
        return f"Invalid expected_confidence: '{exp_conf}'"
    return None


# ── Per-case evaluation ────────────────────────────────────────────────────────

def _base_fields(entry: dict) -> dict:
    return {
        "case_id": entry["case_id"],
        "scenario": entry["scenario"],
        "boundary_type": entry["boundary_type"],
        "expected_confidence": entry["expected_confidence"],
        "expected_has_caveat": entry["expected_has_caveat"],
        "expected_has_sources": entry["expected_has_sources"],
        "is_boundary_case": entry.get("is_boundary_case", False),
        "n_runs": entry.get("n_runs", 5),
        "keyword_must_include": entry.get("keyword_must_include", []),
        "keyword_must_exclude": entry.get("keyword_must_exclude", []),
    }


def _check_keywords(
    findings_text: str,
    must_include: list[str],
    must_exclude: list[str],
) -> tuple[bool, bool]:
    """Return (include_pass, exclude_pass) for combined key_findings text."""
    include_pass = (
        all(kw.lower() in findings_text.lower() for kw in must_include)
        if must_include else True
    )
    exclude_pass = (
        all(kw.lower() not in findings_text.lower() for kw in must_exclude)
        if must_exclude else True
    )
    return include_pass, exclude_pass


def _evaluate_case(entry: dict, llm) -> dict:
    """Run _synthesise n_runs times for one GT entry; compute consistency metrics."""
    task_description = entry["task_description"]
    raw_results = entry["raw_results"]
    sender_role = entry.get("sender_role", "unknown")
    n_runs = entry.get("n_runs", 5)
    expected_confidence = entry["expected_confidence"]
    expected_has_caveat = entry["expected_has_caveat"]
    expected_has_sources = entry["expected_has_sources"]
    must_include = entry.get("keyword_must_include", [])
    must_exclude = entry.get("keyword_must_exclude", [])

    base = _base_fields(entry)

    pre_err = _precheck_entry(entry)
    if pre_err:
        return {
            **base,
            "error": f"Entry validation failed: {pre_err}",
            "n_valid_runs": 0,
            "confidence_levels_observed": [],
            "confidence_counts": {},
            "modal_confidence": None,
            "consistency_rate": None,
            "confidence_accuracy": None,
            "caveat_accuracy": None,
            "source_attribution_rate": None,
            "keyword_include_rate": None,
            "keyword_exclude_rate": None,
            "flip_count": 0,
            "mean_latency_ms": None,
        }

    runs: list[dict] = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        try:
            summary = _synthesise(task_description, raw_results, llm, sender_role)
            latency_ms = _r((time.perf_counter() - t0) * 1000, 1)

            conf = (summary.confidence or "").lower().strip()
            if conf not in {"high", "medium", "low"}:
                conf = "unknown"

            has_caveat = summary.caveat is not None
            has_sources = bool(summary.sources)

            # Combine all key_findings into one string for keyword guards
            findings_text = " ".join(summary.key_findings or [])
            inc_pass, exc_pass = _check_keywords(findings_text, must_include, must_exclude)

            runs.append({
                "confidence": conf,
                "has_caveat": has_caveat,
                "has_sources": has_sources,
                "keyword_include_pass": inc_pass,
                "keyword_exclude_pass": exc_pass,
                "findings_text": findings_text,
                "latency_ms": latency_ms,
                "error": None,
            })
        except Exception as exc:
            latency_ms = _r((time.perf_counter() - t0) * 1000, 1)
            runs.append({
                "confidence": None,
                "has_caveat": None,
                "has_sources": None,
                "keyword_include_pass": None,
                "keyword_exclude_pass": None,
                "findings_text": "",
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
            "caveat_accuracy": None,
            "source_attribution_rate": None,
            "keyword_include_rate": None,
            "keyword_exclude_rate": None,
            "flip_count": 0,
            "mean_latency_ms": None,
        }

    # ── Confidence metrics ────────────────────────────────────────────────────
    conf_levels = [r["confidence"] for r in valid_runs]
    conf_counts = Counter(conf_levels)
    modal_confidence = conf_counts.most_common(1)[0][0]

    consistency_rate = _r(conf_counts[modal_confidence] / n_valid)
    confidence_accuracy = _r(conf_counts.get(expected_confidence, 0) / n_valid)
    flip_count = n_valid - conf_counts[modal_confidence]

    # ── Caveat accuracy ───────────────────────────────────────────────────────
    caveat_accuracy = _r(
        sum(1 for r in valid_runs if r["has_caveat"] == expected_has_caveat) / n_valid
    )

    # ── Source attribution rate ───────────────────────────────────────────────
    source_attribution_rate = _r(
        sum(1 for r in valid_runs if r["has_sources"] == expected_has_sources) / n_valid
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

    mean_latency = (
        _r(sum(r["latency_ms"] for r in valid_runs) / n_valid, 1)
        if valid_runs else None
    )

    return {
        **base,
        "error": None,
        "n_valid_runs": n_valid,
        "confidence_levels_observed": conf_levels,
        "confidence_counts": dict(conf_counts),
        "modal_confidence": modal_confidence,
        "consistency_rate": consistency_rate,
        "confidence_accuracy": confidence_accuracy,
        "caveat_accuracy": caveat_accuracy,
        "source_attribution_rate": source_attribution_rate,
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

    overall = {
        "n_total": len(df),
        "n_valid": len(valid),
        "n_errors": int(df["error"].notna().sum()),
        "n_boundary_cases": int(valid["is_boundary_case"].sum()) if len(valid) else 0,
        "mean_confidence_accuracy": safe_mean(valid["confidence_accuracy"]),
        "mean_caveat_accuracy": safe_mean(valid["caveat_accuracy"]),
        "mean_source_attribution_rate": safe_mean(valid["source_attribution_rate"]),
        "mean_consistency_rate": safe_mean(valid["consistency_rate"]),
        "flip_rate": _r(float((valid["flip_count"] > 0).mean())) if len(valid) else None,
        "total_flip_count": int(valid["flip_count"].sum()) if len(valid) else 0,
        "mean_latency_ms": safe_mean(valid["mean_latency_ms"]),
        "p95_latency_ms": (
            _r(float(valid["mean_latency_ms"].dropna().quantile(0.95)), 1)
            if valid["mean_latency_ms"].notna().any() else None
        ),
    }

    kw_inc = valid["keyword_include_rate"].dropna()
    kw_exc = valid["keyword_exclude_rate"].dropna()
    overall["keyword_include_rate"] = _r(float(kw_inc.mean())) if len(kw_inc) else None
    overall["keyword_exclude_rate"] = _r(float(kw_exc.mean())) if len(kw_exc) else None

    # Per expected confidence level breakdown
    by_level: dict = {}
    if len(valid):
        for lvl, grp in valid.groupby("expected_confidence"):
            by_level[str(lvl)] = {
                "n": len(grp),
                "mean_confidence_accuracy": safe_mean(grp["confidence_accuracy"]),
                "mean_caveat_accuracy": safe_mean(grp["caveat_accuracy"]),
                "mean_source_attribution_rate": safe_mean(grp["source_attribution_rate"]),
                "mean_consistency_rate": safe_mean(grp["consistency_rate"]),
                "flip_rate": (
                    _r(float((grp["flip_count"] > 0).mean())) if len(grp) else None
                ),
            }

    # Per boundary_type breakdown
    by_boundary: dict = {}
    if len(valid):
        for bt, grp in valid.groupby("boundary_type"):
            by_boundary[str(bt)] = {
                "n": len(grp),
                "mean_confidence_accuracy": safe_mean(grp["confidence_accuracy"]),
                "mean_consistency_rate": safe_mean(grp["consistency_rate"]),
                "flip_rate": (
                    _r(float((grp["flip_count"] > 0).mean())) if len(grp) else None
                ),
            }

    # Observed confidence distribution per expected group
    conf_distribution: dict = {}
    for lvl in ["high", "medium", "low"]:
        dist = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        subset = (
            valid[valid["expected_confidence"] == lvl]
            if len(valid) else pd.DataFrame()
        )
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
                "case_id", "boundary_type", "expected_confidence",
                "modal_confidence", "confidence_accuracy", "caveat_accuracy",
                "source_attribution_rate", "consistency_rate", "flip_count",
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
    ax.axhline(
        THRESHOLDS["confidence_accuracy"]["ok"] * 100,
        color="green", linestyle="--", linewidth=1,
        label=f"OK ≥ {THRESHOLDS['confidence_accuracy']['ok']*100:.0f}%",
    )
    ax.axhline(
        THRESHOLDS["confidence_accuracy"]["warn"] * 100,
        color="orange", linestyle=":", linewidth=1,
        label=f"Warn ≥ {THRESHOLDS['confidence_accuracy']['warn']*100:.0f}%",
    )
    ax.set_ylim(0, 115)
    ax.set_ylabel("Confidence Accuracy (%)")
    ax.set_title("Confidence Level Accuracy by Expected Level\n(% of runs matching expected_confidence)")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, conf_acc_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=10,
        )

    # ── Panel 2: Caveat & source attribution accuracy per case ────────────────
    ax = axes[1]
    if len(valid):
        case_ids = valid["case_id"].tolist()
        caveat_accs = [
            v * 100 if v is not None else 0
            for v in valid["caveat_accuracy"].tolist()
        ]
        source_accs = [
            v * 100 if v is not None else 0
            for v in valid["source_attribution_rate"].tolist()
        ]
        x = np.arange(len(case_ids))
        w = 0.38
        ax.bar(x - w / 2, caveat_accs, w, label="Caveat accuracy",
               color="steelblue", alpha=0.82)
        ax.bar(x + w / 2, source_accs, w, label="Source attribution",
               color="mediumpurple", alpha=0.82)
        ax.axhline(
            THRESHOLDS["caveat_accuracy"]["ok"] * 100,
            color="steelblue", linestyle="--", linewidth=0.8, alpha=0.7,
        )
        ax.axhline(
            THRESHOLDS["source_attribution_rate"]["ok"] * 100,
            color="mediumpurple", linestyle="--", linewidth=0.8, alpha=0.7,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(case_ids, rotation=45, ha="right", fontsize=7)
        ax.set_ylim(0, 115)
        ax.set_ylabel("Accuracy (%)")
        ax.set_title("Caveat & Source Attribution Accuracy per Case")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center",
                transform=ax.transAxes)

    # ── Panel 3: Observed confidence distribution by expected group (stacked) ─
    ax = axes[2]
    conf_dist = aggregated["conf_distribution"]
    groups = [g for g in ["high", "medium", "low"] if g in conf_dist]
    h_counts = [conf_dist[g].get("high", 0) for g in groups]
    m_counts = [conf_dist[g].get("medium", 0) for g in groups]
    l_counts = [conf_dist[g].get("low", 0) for g in groups]
    x = np.arange(len(groups))
    bar_w = 0.5
    ax.bar(x, h_counts, bar_w, label="Observed: high",
           color="mediumseagreen", alpha=0.85)
    ax.bar(x, m_counts, bar_w, bottom=h_counts,
           label="Observed: medium", color="goldenrod", alpha=0.85)
    ax.bar(
        x, l_counts, bar_w,
        bottom=[h + m for h, m in zip(h_counts, m_counts)],
        label="Observed: low", color="coral", alpha=0.85,
    )
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
        ax.set_title("Consistency Rate Distribution\n(% of n_runs matching modal confidence)")
        from matplotlib.patches import Patch
        ax.legend(handles=[
            Patch(facecolor="coral", alpha=0.85, label="< 60% (unstable)"),
            Patch(facecolor="goldenrod", alpha=0.85, label="60–90% (marginal)"),
            Patch(facecolor="mediumseagreen", alpha=0.85, label="> 90% (stable)"),
        ], fontsize=8)
    else:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center",
                transform=ax.transAxes)

    # ── Panel 5: Summary scoreboard ───────────────────────────────────────────
    ax = axes[4]
    metrics = [
        ("Confidence Accuracy", overall.get("mean_confidence_accuracy"), "confidence_accuracy", False),
        ("Caveat Accuracy",     overall.get("mean_caveat_accuracy"),     "caveat_accuracy",     False),
        ("Source Attribution",  overall.get("mean_source_attribution_rate"), "source_attribution_rate", False),
        ("Consistency Rate",    overall.get("mean_consistency_rate"),    "consistency_rate",    False),
        ("Flip Rate",           overall.get("flip_rate"),                "flip_rate",           True),
    ]
    labels = [m[0] for m in metrics]
    vals = [m[1] or 0 for m in metrics]
    colors_sb = [
        _bar_color(v, m[2], lower=m[3])
        for v, m in zip(vals, metrics)
    ]
    bars_sb = ax.barh(
        labels, [v * 100 for v in vals],
        color=colors_sb, alpha=0.85,
    )
    ax.set_xlim(0, 115)
    ax.set_xlabel("Score (%)")
    ax.set_title("Overall Metric Scoreboard\n(green = OK, amber = warn, red = below threshold)")
    for bar, val in zip(bars_sb, vals):
        ax.text(
            bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
            f"{val*100:.1f}%", va="center", fontsize=9,
        )

    # ── Panel 6: Keyword guard rates ──────────────────────────────────────────
    ax = axes[5]
    kw_cases = [
        r for r in per_case
        if r.get("error") is None and (
            r.get("keyword_include_rate") is not None
            or r.get("keyword_exclude_rate") is not None
        )
    ]
    if kw_cases:
        kw_ids = [r["case_id"] for r in kw_cases]
        inc_rates = [
            (r["keyword_include_rate"] or 0) * 100
            if r.get("keyword_include_rate") is not None else None
            for r in kw_cases
        ]
        exc_rates = [
            (r["keyword_exclude_rate"] or 0) * 100
            if r.get("keyword_exclude_rate") is not None else None
            for r in kw_cases
        ]
        x = np.arange(len(kw_ids))
        w = 0.38
        inc_vals = [v if v is not None else 0 for v in inc_rates]
        exc_vals = [v if v is not None else 0 for v in exc_rates]
        ax.bar(x - w / 2, inc_vals, w, label="Include rate",
               color="teal", alpha=0.82)
        ax.bar(x + w / 2, exc_vals, w, label="Exclude rate",
               color="darkorange", alpha=0.82)
        ax.axhline(
            THRESHOLDS["keyword_rate"]["ok"] * 100,
            color="green", linestyle="--", linewidth=1,
            label=f"OK = {THRESHOLDS['keyword_rate']['ok']*100:.0f}%",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(kw_ids, rotation=45, ha="right", fontsize=7)
        ax.set_ylim(0, 115)
        ax.set_ylabel("Rate (%)")
        ax.set_title("Keyword Guard Rates\n(include = must contain; exclude = must not contain)")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No keyword guards defined", ha="center", va="center",
                transform=ax.transAxes)

    plt.suptitle("Research Agent — Synthesis Evaluation Report", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    chart_path = RESULTS_DIR / "research_agent_charts.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved -> {chart_path}")


# ── Threshold check ────────────────────────────────────────────────────────────

def _check_thresholds(aggregated: dict) -> None:
    overall = aggregated["overall"]
    checks = [
        ("mean_confidence_accuracy",     "confidence_accuracy",     False),
        ("mean_caveat_accuracy",         "caveat_accuracy",         False),
        ("mean_source_attribution_rate", "source_attribution_rate", False),
        ("mean_consistency_rate",        "consistency_rate",        False),
        ("flip_rate",                    "flip_rate",               True),
    ]
    print("\n── Threshold Summary ─────────────────────────────────────────────")
    for key, threshold_key, lower_is_better in checks:
        val = overall.get(key)
        if val is None:
            print(f"  [--] {key:<35} N/A")
            continue
        t = THRESHOLDS[threshold_key]
        ok_thresh, warn_thresh = t["ok"], t["warn"]
        if lower_is_better:
            status = "OK" if val <= ok_thresh else "WARN" if val <= warn_thresh else "FAIL"
        else:
            status = "OK" if val >= ok_thresh else "WARN" if val >= warn_thresh else "FAIL"
        print(f"  [{status}] {key:<35} {val*100:.1f}%")


# ── Main ───────────────────────────────────────────────────────────────────────

def main(case_filter: str | None = None, n_runs_override: int | None = None) -> None:
    if not GT_PATH.exists():
        print(
            f"[ERROR] Ground truth not found at {GT_PATH}\n"
            "Generate it first:\n"
            "  uv run python tests/research_agent/generate_ground_truth.py"
        )
        return

    with open(GT_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    entries = dataset["entries"]
    if case_filter:
        entries = [e for e in entries if e["case_id"] == case_filter]
        if not entries:
            print(f"[ERROR] No case found with case_id='{case_filter}'")
            return

    if n_runs_override is not None:
        for e in entries:
            e["n_runs"] = n_runs_override

    print(f"Research Agent Evaluation — {len(entries)} case(s)")
    print(f"Ground truth version: {dataset['metadata'].get('version', '?')}\n")

    llm = get_chat_llm(temperature=0.0)

    per_case: list[dict] = []
    for i, entry in enumerate(entries, 1):
        n = entry.get("n_runs", 5)
        print(f"  [{i:02d}/{len(entries):02d}] {entry['case_id']}  ({n} runs)  {entry['scenario'][:60]}...")
        result = _evaluate_case(entry, llm)
        per_case.append(result)
        if result["error"]:
            print(f"         ERROR: {result['error']}")
        else:
            conf_acc = result["confidence_accuracy"]
            cav_acc = result["caveat_accuracy"]
            src_acc = result["source_attribution_rate"]
            flip = result["flip_count"]
            print(
                f"         conf_acc={conf_acc*100:.0f}%  "
                f"caveat_acc={cav_acc*100:.0f}%  "
                f"src_acc={src_acc*100:.0f}%  "
                f"flip={flip}  modal={result['modal_confidence']}"
            )

    aggregated = _aggregate(per_case)
    _check_thresholds(aggregated)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "n_cases": len(per_case),
        "aggregated": aggregated,
        "per_case": per_case,
    }
    metrics_path = RESULTS_DIR / "research_agent_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nMetrics saved -> {metrics_path}")

    if len(per_case) > 1:
        _make_charts(per_case, aggregated)

    overall = aggregated["overall"]
    print("\n── Overall ───────────────────────────────────────────────────────")
    print(f"  Cases evaluated         : {overall['n_valid']} / {overall['n_total']}")
    print(f"  Boundary cases          : {overall['n_boundary_cases']}")
    print(f"  Mean confidence accuracy: {(overall['mean_confidence_accuracy'] or 0)*100:.1f}%")
    print(f"  Mean caveat accuracy    : {(overall['mean_caveat_accuracy'] or 0)*100:.1f}%")
    print(f"  Mean source attribution : {(overall['mean_source_attribution_rate'] or 0)*100:.1f}%")
    print(f"  Mean consistency rate   : {(overall['mean_consistency_rate'] or 0)*100:.1f}%")
    print(f"  Flip rate               : {(overall['flip_rate'] or 0)*100:.1f}%")
    print(f"  Mean latency            : {overall.get('mean_latency_ms', 'N/A')} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Research agent synthesis evaluation."
    )
    parser.add_argument(
        "--case",
        metavar="CASE_ID",
        help="Run a single case by case_id (e.g. rsch-001).",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        metavar="N",
        help="Override n_runs for all cases (useful for smoke-testing with --n-runs 1).",
    )
    args = parser.parse_args()
    main(case_filter=args.case, n_runs_override=args.n_runs)
