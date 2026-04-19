#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(PAPER_DIR / ".mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(PAPER_DIR / ".cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> None:
    paper_dir = Path(__file__).resolve().parent
    repo_root = paper_dir.parent
    metrics_path = repo_root / "tests" / "policy_agent" / "results" / "answer_metrics.json"
    output_path = paper_dir / "appendix_policy_eval_summary.png"
    mpl_dir = Path(os.environ["MPLCONFIGDIR"])
    mpl_dir.mkdir(parents=True, exist_ok=True)

    metrics = json.loads(metrics_path.read_text())
    aggregated = metrics["aggregated"]

    category_items = sorted(
        aggregated["verdict_accuracy"]["by_category"].items(),
        key=lambda item: item[1]["verdict_accuracy_pct"],
    )
    category_labels = [name.replace("_", "\n") for name, _ in category_items]
    category_scores = [values["verdict_accuracy_pct"] for _, values in category_items]
    category_counts = [values["n"] for _, values in category_items]
    overall_accuracy = aggregated["verdict_accuracy"]["overall_pct"]

    latency = aggregated["latency"]
    latency_labels = ["Search", "Rerank", "Eval", "Total\nmean", "Total\np95"]
    latency_values = [
        latency["search_ms_mean"],
        latency["rerank_ms_mean"],
        latency["eval_ms_mean"],
        latency["total_ms_mean"],
        latency["total_ms_p95"],
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)

    acc_ax = axes[0]
    acc_colors = ["#c2410c" if value < overall_accuracy else "#0f766e" for value in category_scores]
    acc_bars = acc_ax.bar(category_labels, category_scores, color=acc_colors)
    acc_ax.axhline(
        overall_accuracy,
        color="#334155",
        linestyle="--",
        linewidth=1.3,
        label=f"overall {overall_accuracy:.1f}%",
    )
    acc_ax.set_ylim(0, 110)
    acc_ax.set_ylabel("Verdict accuracy (%)")
    acc_ax.set_title("Policy verdict accuracy by category")
    acc_ax.legend(frameon=False, loc="lower right")
    acc_ax.grid(axis="y", alpha=0.25)
    for bar, count, score in zip(acc_bars, category_counts, category_scores):
        acc_ax.text(
            bar.get_x() + bar.get_width() / 2,
            min(score + 2.5, 106),
            f"n={count}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    lat_ax = axes[1]
    lat_colors = ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"]
    lat_bars = lat_ax.bar(latency_labels, latency_values, color=lat_colors)
    lat_ax.set_ylabel("Latency (ms)")
    lat_ax.set_title("Policy pipeline latency")
    lat_ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(lat_bars, latency_values):
        lat_ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(latency_values) * 0.02,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.suptitle("Appendix Policy Evaluation Summary", fontsize=14, y=1.02)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    print(output_path)


if __name__ == "__main__":
    main()
