"""
Risk Node — LLM Second Pass Consistency & Correctness Benchmark

Evaluates the stability and accuracy of the LLM layer in risk_node (risk_llm.py).
Every GT case is designed to produce 'medium' from the deterministic Layer 1 rules,
ensuring the LLM second pass always fires. Each case is then run n_runs times to
measure how consistently and correctly the LLM revises the risk level.

Core metrics (no extra LLM calls beyond the pipeline itself):
    correct_rate           — % of runs matching expected_stable_level
    consistency_rate       — % of runs matching the modal (most frequent) output
    flip_count             — number of runs deviating from the modal
    dangerous_flip         — True if expected=high but any run returned 'low' (critical)
    approval_accuracy      — % of runs with correct requires_approval value
    category_consistency   — % of runs where same LLM flag categories appear

Aggregated across cases:
    mean_consistency_rate  — overall LLM stability signal
    mean_correct_rate      — overall LLM accuracy signal
    dangerous_flip_rate    — ZERO TOLERANCE; any non-zero value is a FAIL

Output:
    tests/risk_node/results/risk_llm_metrics.json
    tests/risk_node/results/risk_llm_charts.png

Usage:
    uv run python tests/risk_node/evaluate.py

Prerequisites:
    1. Ground truth dataset at tests/risk_node/test_cases/ground_truth_dataset.json
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

from backend.nodes.approval_rules import approval_rule_node
from backend.nodes.risk import risk_node
from backend.nodes.risk_rules import (
    aggregate_risk,
    check_confidence,
    check_disclosure,
    check_escalation_triggers,
    check_intent_urgency,
    check_pii_leakage,
    check_policy_cross,
    check_role_sensitivity,
    check_tone,
    check_unverified_claims,
    scan_for_risky_keywords,
)

# ── Paths ──────────────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results"
GT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# Pass / warn thresholds
THRESHOLDS = {
    "correct_rate":         {"ok": 0.90, "warn": 0.80},
    "consistency_rate":     {"ok": 0.90, "warn": 0.75},
    "approval_accuracy":    {"ok": 0.95, "warn": 0.85},
    "category_consistency": {"ok": 0.80, "warn": 0.65},
    "flip_rate":            {"ok": 0.20, "warn": 0.40},   # lower is better
}


def _r(v, n: int = 4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


# ── Layer 1 pre-validation ─────────────────────────────────────────────────────

def _compute_layer1(state: dict) -> tuple[str, list[str]]:
    """Replicate the deterministic Layer 1 of risk_node without invoking the LLM.

    Returns (risk_level, flags). Used to confirm each GT case reliably
    produces 'medium' so the LLM second pass always fires.
    """
    reply_text: str = state.get("reply_text", "")
    sender_role: str = state.get("sender_role", "unknown")
    completed_tasks: list = state.get("completed_tasks", [])
    confidence_level: str = state.get("confidence_level", "")
    confidence_note: str = state.get("confidence_note", "")
    unverified_claims: list = state.get("unverified_claims", [])
    tone_flags_: list = state.get("tone_flags", [])
    intent_label: str = state.get("intent_label", "")
    urgency_level: str = state.get("urgency_level", "")

    if (sender_role or "").lower() == "owner":
        return "low", []

    approval_result = approval_rule_node(state)
    approval_flags = list(approval_result.get("approval_rule_flags", []))

    flags: list[str] = []
    flags.extend(approval_flags)
    flags.extend(scan_for_risky_keywords(reply_text))
    flags.extend(check_disclosure(reply_text, sender_role))
    flags.extend(check_escalation_triggers(reply_text))
    flags.extend(check_pii_leakage(reply_text))
    flags.extend(check_role_sensitivity(reply_text, sender_role))
    flags.extend(check_policy_cross(completed_tasks))
    flags.extend(check_unverified_claims(reply_text, completed_tasks))
    flags.extend(check_confidence(confidence_level, confidence_note, unverified_claims))
    flags.extend(check_tone(tone_flags_))
    flags.extend(check_intent_urgency(intent_label, urgency_level))

    level, _ = aggregate_risk(flags)
    return level, flags


# ── Flag category extraction ───────────────────────────────────────────────────

def _extract_llm_categories(risk_flags: list[str]) -> frozenset[str]:
    """Extract category labels from LLM-added flags (those starting with 'LLM: ').

    risk_llm.py prefixes each additional flag with 'LLM: ' and expects the
    LLM to begin the flag body with a category label (e.g. 'IMPLIED COMMITMENT: ...').
    """
    cats: set[str] = set()
    for f in risk_flags:
        if not f.startswith("LLM: "):
            continue
        body = f[5:]  # strip "LLM: "
        if ":" in body:
            cats.add(body.split(":")[0].strip().upper())
        elif body.strip():
            cats.add(body.strip()[:40].upper())
    return frozenset(cats)


# ── Per-case evaluation ────────────────────────────────────────────────────────

def _base_fields(entry: dict) -> dict:
    return {
        "case_id": entry["case_id"],
        "scenario": entry["scenario"],
        "boundary_type": entry["boundary_type"],
        "expected_stable_level": entry["expected_stable_level"],
        "expected_requires_approval": entry["expected_requires_approval"],
        "is_boundary_case": entry.get("is_boundary_case", False),
        "n_runs": entry.get("n_runs", 5),
    }


def _evaluate_case(entry: dict) -> dict:
    """Run risk_node n_runs times for one GT entry; compute consistency metrics."""
    state = entry["state"]
    n_runs = entry.get("n_runs", 5)
    expected_level = entry["expected_stable_level"]
    expected_approval = entry["expected_requires_approval"]
    case_id = entry["case_id"]

    base = _base_fields(entry)

    # ── Pre-validate Layer 1 ──────────────────────────────────────────────────
    try:
        layer1_level, layer1_flags = _compute_layer1(state)
    except Exception as exc:
        return {
            **base,
            "error": f"Layer 1 validation error: {exc}",
            "layer1_level": None,
            "layer1_correct": False,
            "layer1_flags": [],
            "n_valid_runs": 0,
            "levels_observed": [],
            "level_counts": {},
            "modal_level": None,
            "consistency_rate": None,
            "correct_rate": None,
            "flip_count": 0,
            "dangerous_flip": False,
            "approval_accuracy": None,
            "category_consistency_rate": None,
            "modal_categories": [],
            "mean_latency_ms": None,
        }

    layer1_correct = layer1_level == "medium"
    if not layer1_correct:
        print(
            f"  [WARN] {case_id}: Layer 1 produced '{layer1_level}' not 'medium'. "
            f"LLM second pass may not fire. Flags: {layer1_flags}"
        )

    # ── Run risk_node N times ─────────────────────────────────────────────────
    runs: list[dict] = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        try:
            result = risk_node(dict(state))   # shallow copy avoids state mutation
            latency_ms = _r((time.perf_counter() - t0) * 1000, 1)
            runs.append({
                "final_level": result["risk_level"],
                "requires_approval": result["requires_approval"],
                "risk_flags": list(result["risk_flags"]),
                "latency_ms": latency_ms,
                "error": None,
            })
        except Exception as exc:
            latency_ms = _r((time.perf_counter() - t0) * 1000, 1)
            runs.append({
                "final_level": None,
                "requires_approval": None,
                "risk_flags": [],
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
            "layer1_level": layer1_level,
            "layer1_correct": layer1_correct,
            "layer1_flags": layer1_flags,
            "n_valid_runs": 0,
            "levels_observed": [],
            "level_counts": {},
            "modal_level": None,
            "consistency_rate": None,
            "correct_rate": None,
            "flip_count": 0,
            "dangerous_flip": False,
            "approval_accuracy": None,
            "category_consistency_rate": None,
            "modal_categories": [],
            "mean_latency_ms": None,
        }

    # ── Consistency & correctness ─────────────────────────────────────────────
    levels = [r["final_level"] for r in valid_runs]
    level_counts = Counter(levels)
    modal_level = level_counts.most_common(1)[0][0]

    consistency_rate = _r(level_counts[modal_level] / n_valid)
    correct_rate = _r(level_counts.get(expected_level, 0) / n_valid)
    flip_count = n_valid - level_counts[modal_level]

    # Dangerous flip: expected 'high' but LLM returned 'low' in any run
    dangerous_flip = (expected_level == "high") and ("low" in levels)

    # ── Approval accuracy ─────────────────────────────────────────────────────
    approval_hits = [r for r in valid_runs if r["requires_approval"] == expected_approval]
    approval_accuracy = _r(len(approval_hits) / n_valid)

    # ── LLM flag category consistency ─────────────────────────────────────────
    cats_per_run = [_extract_llm_categories(r["risk_flags"]) for r in valid_runs]
    cat_counts = Counter(cats_per_run)
    modal_cats = cat_counts.most_common(1)[0][0]
    category_consistency_rate = _r(cat_counts[modal_cats] / n_valid)

    mean_latency = _r(
        sum(r["latency_ms"] for r in valid_runs) / n_valid, 1
    ) if valid_runs else None

    return {
        **base,
        "error": None,
        "layer1_level": layer1_level,
        "layer1_correct": layer1_correct,
        "layer1_flags": layer1_flags,
        "n_valid_runs": n_valid,
        "levels_observed": levels,
        "level_counts": dict(level_counts),
        "modal_level": modal_level,
        "consistency_rate": consistency_rate,
        "correct_rate": correct_rate,
        "flip_count": flip_count,
        "dangerous_flip": dangerous_flip,
        "approval_accuracy": approval_accuracy,
        "category_consistency_rate": category_consistency_rate,
        "modal_categories": sorted(modal_cats),
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
        "n_layer1_medium_confirmed": int(valid["layer1_correct"].sum()) if len(valid) else 0,
        "n_boundary_cases": int(valid["is_boundary_case"].sum()) if len(valid) else 0,
        # Randomness / consistency
        "mean_consistency_rate": safe_mean(valid["consistency_rate"]),
        "mean_correct_rate": safe_mean(valid["correct_rate"]),
        "mean_approval_accuracy": safe_mean(valid["approval_accuracy"]),
        "mean_category_consistency": safe_mean(valid["category_consistency_rate"]),
        # Flip metrics
        "flip_rate": _r(float((valid["flip_count"] > 0).mean())) if len(valid) else None,
        "total_flip_count": int(valid["flip_count"].sum()) if len(valid) else 0,
        "dangerous_flip_rate": _r(float(valid["dangerous_flip"].mean())) if len(valid) else None,
        "n_dangerous_flips": int(valid["dangerous_flip"].sum()) if len(valid) else 0,
        # Latency
        "mean_latency_ms": safe_mean(valid["mean_latency_ms"]),
        "p95_latency_ms": (
            _r(float(valid["mean_latency_ms"].dropna().quantile(0.95)), 1)
            if valid["mean_latency_ms"].notna().any() else None
        ),
    }

    # Per expected_stable_level breakdown
    by_level: dict = {}
    if len(valid):
        for lvl, grp in valid.groupby("expected_stable_level"):
            by_level[str(lvl)] = {
                "n": len(grp),
                "mean_correct_rate": safe_mean(grp["correct_rate"]),
                "mean_consistency_rate": safe_mean(grp["consistency_rate"]),
                "flip_rate": _r(float((grp["flip_count"] > 0).mean())) if len(grp) else None,
                "n_dangerous_flips": int(grp["dangerous_flip"].sum()),
            }

    # Per boundary_type breakdown (condensed)
    by_boundary: dict = {}
    if len(valid):
        for bt, grp in valid.groupby("boundary_type"):
            by_boundary[str(bt)] = {
                "n": len(grp),
                "mean_correct_rate": safe_mean(grp["correct_rate"]),
                "mean_consistency_rate": safe_mean(grp["consistency_rate"]),
                "flip_rate": _r(float((grp["flip_count"] > 0).mean())) if len(grp) else None,
                "n_dangerous_flips": int(grp["dangerous_flip"].sum()),
            }

    # Level distribution across all runs, grouped by expected level
    # For each expected level: how many total runs produced high/medium/low?
    level_distribution: dict = {}
    for lvl in ["high", "medium", "low"]:
        dist = {"high": 0, "medium": 0, "low": 0}
        subset = valid[valid["expected_stable_level"] == lvl] if len(valid) else pd.DataFrame()
        for _, row in subset.iterrows():
            for obs in (row.get("levels_observed") or []):
                if obs in dist:
                    dist[obs] += 1
        level_distribution[lvl] = dist

    # Worst cases by correct_rate
    worst: list[dict] = []
    if len(valid):
        worst = (
            valid.nsmallest(5, "correct_rate")
            [[
                "case_id", "boundary_type", "expected_stable_level",
                "modal_level", "correct_rate", "consistency_rate",
                "flip_count", "dangerous_flip",
            ]]
            .to_dict(orient="records")
        )

    return {
        "overall": overall,
        "by_expected_level": by_level,
        "by_boundary_type": by_boundary,
        "level_distribution": level_distribution,
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

    # ── Panel 1: Correct rate by expected_stable_level ────────────────────────
    ax = axes[0]
    levels_order = [l for l in ["high", "medium", "low"] if l in by_level]
    corr_vals = [by_level[l]["mean_correct_rate"] or 0 for l in levels_order]
    colors = [
        "mediumseagreen" if v >= THRESHOLDS["correct_rate"]["ok"]
        else "goldenrod" if v >= THRESHOLDS["correct_rate"]["warn"]
        else "coral"
        for v in corr_vals
    ]
    bars = ax.bar(levels_order, [v * 100 for v in corr_vals], color=colors, alpha=0.85)
    ax.axhline(
        THRESHOLDS["correct_rate"]["ok"] * 100, color="green", linestyle="--",
        linewidth=1, label=f"OK ≥ {THRESHOLDS['correct_rate']['ok']*100:.0f}%",
    )
    ax.axhline(
        THRESHOLDS["correct_rate"]["warn"] * 100, color="orange", linestyle=":",
        linewidth=1, label=f"Warn ≥ {THRESHOLDS['correct_rate']['warn']*100:.0f}%",
    )
    ax.set_ylim(0, 115)
    ax.set_ylabel("Correct Rate (%)")
    ax.set_title("LLM Correct Rate by Expected Level\n(% of runs matching expected_stable_level)")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, corr_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
            f"{val*100:.1f}%", ha="center", va="bottom", fontsize=10,
        )

    # ── Panel 2: Consistency rate distribution (histogram) ────────────────────
    ax = axes[1]
    if len(valid) and valid["consistency_rate"].notna().any():
        rates = valid["consistency_rate"].dropna() * 100
        bins = [0, 20, 40, 60, 80, 90, 100, 101]
        counts, edges = np.histogram(rates, bins=bins)
        bar_labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–90%", "90–100%", "100%"]
        bar_colors = [
            "coral" if edge_r <= 60
            else "goldenrod" if edge_r <= 90
            else "mediumseagreen"
            for edge_r in edges[1:]
        ]
        ax.bar(range(len(counts)), counts, color=bar_colors, alpha=0.85, width=0.7)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(bar_labels, fontsize=8)
        ax.set_ylabel("Number of Cases")
        ax.set_title(
            "Consistency Rate Distribution\n(how stable is the LLM across n_runs per case)"
        )
        # Threshold reference lines as patches in legend
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
    ax.set_title("Consistency Rate Distribution\n(% of n_runs matching modal output)")

    # ── Panel 3: Level distribution by expected group (stacked bar) ───────────
    ax = axes[2]
    level_dist = aggregated["level_distribution"]
    groups = [g for g in ["high", "medium", "low"] if g in level_dist]
    high_counts = [level_dist[g].get("high", 0) for g in groups]
    med_counts  = [level_dist[g].get("medium", 0) for g in groups]
    low_counts  = [level_dist[g].get("low", 0) for g in groups]
    x = np.arange(len(groups))
    bar_w = 0.5
    b1 = ax.bar(x, high_counts, bar_w, label="Observed: high", color="mediumseagreen", alpha=0.85)
    b2 = ax.bar(x, med_counts, bar_w, bottom=high_counts, label="Observed: medium", color="goldenrod", alpha=0.85)
    b3 = ax.bar(
        x, low_counts, bar_w,
        bottom=[h + m for h, m in zip(high_counts, med_counts)],
        label="Observed: low", color="coral", alpha=0.85,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([f"Expected:\n{g}" for g in groups])
    ax.set_ylabel("Total run count across all cases in group")
    ax.set_title("Observed Level Distribution by Expected Group\n(ideal: green dominates each bar)")
    ax.legend(fontsize=8)
    # Annotate totals
    totals = [h + m + l for h, m, l in zip(high_counts, med_counts, low_counts)]
    for xi, tot in zip(x, totals):
        if tot > 0:
            ax.text(xi, tot + 0.5, f"n={tot}", ha="center", va="bottom", fontsize=9)

    # ── Panel 4: Flip rate by expected_stable_level ───────────────────────────
    ax = axes[3]
    flip_vals = [by_level.get(l, {}).get("flip_rate") or 0 for l in levels_order]
    dan_counts = [by_level.get(l, {}).get("n_dangerous_flips") or 0 for l in levels_order]
    bar_colors_flip = [
        "coral" if v > THRESHOLDS["flip_rate"]["warn"]
        else "goldenrod" if v > THRESHOLDS["flip_rate"]["ok"]
        else "mediumseagreen"
        for v in flip_vals
    ]
    bars_f = ax.bar(levels_order, [v * 100 for v in flip_vals], color=bar_colors_flip, alpha=0.85)
    ax.axhline(
        THRESHOLDS["flip_rate"]["ok"] * 100, color="green", linestyle="--",
        linewidth=1, label=f"OK ≤ {THRESHOLDS['flip_rate']['ok']*100:.0f}%",
    )
    ax.axhline(
        THRESHOLDS["flip_rate"]["warn"] * 100, color="orange", linestyle=":",
        linewidth=1, label=f"Warn ≤ {THRESHOLDS['flip_rate']['warn']*100:.0f}%",
    )
    ax.set_ylim(0, max(max(flip_vals) * 100 + 15, 50))
    ax.set_ylabel("Flip Rate (% of cases with any run mismatch)")
    ax.set_title("Flip Rate by Expected Level\n(lower is better — ⚠ red annotation = dangerous flip)")
    ax.legend(fontsize=8)
    for bar, val, dan in zip(bars_f, flip_vals, dan_counts):
        label = f"{val*100:.0f}%"
        if dan > 0:
            label += f"\n⚠ {dan} dangerous"
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            label, ha="center", va="bottom", fontsize=9,
            color="darkred" if dan > 0 else "black",
        )

    # ── Panel 5: Mean latency per boundary_type group ─────────────────────────
    ax = axes[4]
    # Condense boundary_types into 4 broad groups for readability
    def _group(bt: str) -> str:
        if bt.startswith("implied") or bt in ("factual_contradiction", "contextual_liability",
                                               "intent_mismatch", "policy_approval_violated"):
            return "upgrade → high"
        if bt.startswith("maintain"):
            return "maintain medium"
        if bt.startswith("false_positive"):
            return "downgrade → low"
        return "boundary"

    if len(valid):
        valid_lat = valid.copy()
        valid_lat["group"] = valid_lat["boundary_type"].apply(_group)
        grp_lat = valid_lat.groupby("group")["mean_latency_ms"].mean()
        group_order = [g for g in ["upgrade → high", "maintain medium", "downgrade → low", "boundary"]
                       if g in grp_lat.index]
        lat_vals = [grp_lat.get(g, 0) for g in group_order]
        bars_l = ax.bar(group_order, lat_vals, color="mediumpurple", alpha=0.85)
        ax.set_xticklabels(group_order, fontsize=8, rotation=10)
        ax.set_ylabel("Mean Latency (ms)")
        ax.set_title("Mean LLM Second Pass Latency\nby Scenario Group")
        for bar, val in zip(bars_l, lat_vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                f"{val:.0f} ms", ha="center", va="bottom", fontsize=9,
            )
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

    def _zero_tag(v):
        if v is None:
            return ""
        return "[OK]" if v == 0.0 else "[FAIL]"

    scorecard = [
        ("Mean correct rate",
         f"{_fmt_pct(overall['mean_correct_rate'])}  {_tag(overall['mean_correct_rate'], 'correct_rate')}"),
        ("Mean consistency rate",
         f"{_fmt_pct(overall['mean_consistency_rate'])}  {_tag(overall['mean_consistency_rate'], 'consistency_rate')}"),
        ("Mean approval accuracy",
         f"{_fmt_pct(overall['mean_approval_accuracy'])}  {_tag(overall['mean_approval_accuracy'], 'approval_accuracy')}"),
        ("Mean category consistency",
         f"{_fmt_pct(overall['mean_category_consistency'])}  {_tag(overall['mean_category_consistency'], 'category_consistency')}"),
        ("Flip rate (any run differs)",
         f"{_fmt_pct(overall['flip_rate'])}  {_tag(overall['flip_rate'], 'flip_rate', lower=True)}"),
        ("Dangerous flip rate",
         f"{_fmt_pct(overall['dangerous_flip_rate'])}  {_zero_tag(overall['dangerous_flip_rate'])}"),
        ("Total flip count",        str(overall["total_flip_count"])),
        ("Layer 1 'medium' confirmed", f"{overall['n_layer1_medium_confirmed']} / {overall['n_valid']}"),
        ("Mean latency (LLM pass)",  f"{overall['mean_latency_ms']} ms"),
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
        "Risk Node — LLM Second Pass Consistency & Correctness Benchmark",
        fontsize=12, y=1.01,
    )
    plt.tight_layout()
    out = RESULTS_DIR / "risk_llm_charts.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Charts saved → {out}")


# ── Summary printing ───────────────────────────────────────────────────────────

def _print_summary(aggregated: dict) -> None:
    SEP = "=" * 66
    overall = aggregated["overall"]
    by_level = aggregated["by_expected_level"]

    print(f"\n{SEP}")
    print("RISK NODE — LLM SECOND PASS BENCHMARK SUMMARY")
    print(SEP)
    print(
        f"  Cases evaluated:       {overall['n_valid']}  "
        f"({overall['n_errors']} errors  |  "
        f"{overall['n_boundary_cases']} boundary)"
    )
    print(
        f"  Layer 1 'medium' confirmed: "
        f"{overall['n_layer1_medium_confirmed']} / {overall['n_valid']}"
    )
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

    print("  Overall metrics:")
    print(f"    Mean correct rate:         {_fmt(overall['mean_correct_rate'], 'correct_rate')}")
    print(f"    Mean consistency rate:     {_fmt(overall['mean_consistency_rate'], 'consistency_rate')}")
    print(f"    Mean approval accuracy:    {_fmt(overall['mean_approval_accuracy'], 'approval_accuracy')}")
    print(f"    Mean category consistency: {_fmt(overall['mean_category_consistency'], 'category_consistency')}")
    print(f"    Flip rate (≥1 flip):       {_fmt(overall['flip_rate'], 'flip_rate', lower=True)}")
    print(f"    Dangerous flip rate:       {_fmt(overall['dangerous_flip_rate'], zero_tol=True)}")
    print(f"    Total flip count:          {overall['total_flip_count']}")
    print(f"    Mean latency (LLM pass):   {overall['mean_latency_ms']} ms")
    print(f"    P95 latency:               {overall['p95_latency_ms']} ms")
    print()

    print("  Per expected level breakdown:")
    header = (
        f"  {'Level':<10}{'N':>4}  "
        f"{'Correct':>10}  {'Consist':>10}  {'FlipRate':>10}  {'DangerFlip':>12}"
    )
    print(header)
    print("  " + "-" * 60)
    for lvl in ["high", "medium", "low"]:
        if lvl not in by_level:
            continue
        ld = by_level[lvl]
        dan = ld["n_dangerous_flips"]
        dan_str = f"  ⚠ {dan}" if dan > 0 else "  0"
        print(
            f"  {lvl:<10}{ld['n']:>4}  "
            f"{_fmt(ld['mean_correct_rate']):>10}  "
            f"{_fmt(ld['mean_consistency_rate']):>10}  "
            f"{_fmt(ld['flip_rate'], 'flip_rate', lower=True):>10}  "
            f"{dan_str:>12}"
        )
    print()

    worst = aggregated.get("worst_cases", [])
    if worst:
        print("  Lowest correct-rate cases:")
        for w in worst:
            cr = f"{w['correct_rate']*100:.0f}%" if w["correct_rate"] is not None else "n/a"
            danger = "  ⚠ DANGEROUS FLIP" if w.get("dangerous_flip") else ""
            print(
                f"    [{w['case_id']}] {w['boundary_type']}  "
                f"expected={w['expected_stable_level']}  modal={w['modal_level']}  "
                f"correct={cr}{danger}"
            )
        print()

    print(SEP)


def _print_recommendations(aggregated: dict) -> None:
    overall = aggregated["overall"]
    cr = overall.get("mean_correct_rate") or 0
    cons = overall.get("mean_consistency_rate") or 0
    flip = overall.get("flip_rate") or 0
    dan = overall.get("dangerous_flip_rate") or 0
    appr = overall.get("mean_approval_accuracy") or 0

    print("\n  Recommendations:")

    if dan > 0:
        print(
            "  [FAIL] Dangerous flips detected — 'high' cases returned 'low' in some runs. "
            "CRITICAL: strengthen the LLM system prompt to never downgrade to 'low' "
            "when an implied commitment or contextual liability is present."
        )

    if cr < THRESHOLDS["correct_rate"]["warn"]:
        print(
            "  [FAIL] Correct rate low — LLM is frequently mis-classifying risk level. "
            "Review the prompt examples in risk_llm.py; add concrete few-shot examples "
            "for each boundary_type that is failing."
        )
    elif cr < THRESHOLDS["correct_rate"]["ok"]:
        print(
            "  [WARN] Correct rate borderline — inspect worst_cases in metrics JSON "
            "and refine the category descriptions in _RISK_LLM_PROMPT."
        )

    if cons < THRESHOLDS["consistency_rate"]["warn"]:
        print(
            "  [FAIL] Consistency rate low — LLM output is highly variable across runs. "
            "Verify temperature=0.0 is being applied. Consider switching to a structured "
            "output schema with more constrained fields."
        )
    elif cons < THRESHOLDS["consistency_rate"]["ok"]:
        print(
            "  [WARN] Consistency rate borderline — some cases are flipping. "
            "Review boundary cases in the GT to understand which scenario types drift."
        )

    if flip > THRESHOLDS["flip_rate"]["warn"]:
        print(
            "  [FAIL] Flip rate high — more than 40% of cases have at least one inconsistent run. "
            "The LLM second pass is behaving stochastically despite temperature=0.0. "
            "Check LLM provider sampling settings."
        )
    elif flip > THRESHOLDS["flip_rate"]["ok"]:
        print("  [WARN] Flip rate elevated — monitor across runs and refine boundary case prompts.")

    if appr < THRESHOLDS["approval_accuracy"]["warn"]:
        print(
            "  [FAIL] Approval accuracy low — requires_approval is being set incorrectly. "
            "This propagates directly to the hold-for-approval gate."
        )

    if dan == 0 and cr >= THRESHOLDS["correct_rate"]["ok"] and cons >= THRESHOLDS["consistency_rate"]["ok"]:
        print("  [OK] LLM second pass is stable and accurate. No critical issues detected.")

    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def evaluate_risk_llm() -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)

    if not GT_PATH.exists():
        raise FileNotFoundError(
            f"Ground truth not found: {GT_PATH}\n"
            "Expected: tests/risk_node/test_cases/ground_truth_dataset.json"
        )

    with open(GT_PATH, encoding="utf-8") as f:
        gt_data = json.load(f)
    entries = gt_data["entries"]
    total_runs = sum(e.get("n_runs", 5) for e in entries)
    print(
        f"Ground truth: {len(entries)} cases  |  "
        f"{total_runs} total LLM calls (layer 1 deterministic, layer 2 LLM at temp=0.0)"
    )
    print("Note: Layer 1 is pre-validated per case before running N LLM calls.\n")

    per_case: list[dict] = []
    for i, entry in enumerate(entries, start=1):
        n = entry.get("n_runs", 5)
        bt = entry["boundary_type"]
        exp = entry["expected_stable_level"]
        bmark = "  [BOUNDARY]" if entry.get("is_boundary_case") else ""
        print(f"  [{i:>2}/{len(entries)}] {entry['case_id']}  {bt}  expected={exp}  n_runs={n}{bmark}")
        result = _evaluate_case(entry)
        if result.get("error"):
            print(f"         ERROR: {result['error']}")
        else:
            cr = result["correct_rate"]
            cons = result["consistency_rate"]
            dan = "  ⚠ DANGEROUS FLIP" if result.get("dangerous_flip") else ""
            print(
                f"         layer1={result['layer1_level']}  "
                f"modal={result['modal_level']}  "
                f"correct={cr*100:.0f}%  "
                f"consist={cons*100:.0f}%  "
                f"flips={result['flip_count']}/{n}{dan}"
            )
        per_case.append(result)

    print(f"\nCompleted {len(per_case)} cases.\n")

    aggregated = _aggregate(per_case)

    metrics = {
        "n_cases": len(per_case),
        "aggregated": aggregated,
        "per_case": [
            {k: v for k, v in r.items() if k not in ("levels_observed", "layer1_flags")}
            for r in per_case
        ],
        # Keep full per-case detail in a separate key for debugging
        "per_case_detail": per_case,
    }

    out_json = RESULTS_DIR / "risk_llm_metrics.json"
    with open(out_json, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"Metrics saved → {out_json}")

    _make_charts(per_case, aggregated)
    _print_summary(aggregated)
    _print_recommendations(aggregated)

    return metrics


if __name__ == "__main__":
    evaluate_risk_llm()
