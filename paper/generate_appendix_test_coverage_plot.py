#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(PAPER_DIR / ".mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(PAPER_DIR / ".cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


# Counts are derived from the collected output of:
# python -m pytest tests/test_pipeline_integration.py tests/test_risk_node.py
# tests/test_p2_risk_rules.py tests/test_approval_rules.py
# tests/test_identity_resolution.py tests/test_discount_negotiation.py
# --collect-only -q
COLLECTED_COUNTS = {
    "test_risk_node.py": 76,
    "test_p2_risk_rules.py": 15,
    "test_approval_rules.py": 5,
    "test_pipeline_integration.py": 4,
    "test_identity_resolution.py": 4,
    "test_discount_negotiation.py": 2,
}


def main() -> None:
    paper_dir = Path(__file__).resolve().parent
    output_path = paper_dir / "appendix_test_coverage_summary.png"
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

    ordered = [
        ("Risk node", COLLECTED_COUNTS["test_risk_node.py"]),
        ("P2 risk rules", COLLECTED_COUNTS["test_p2_risk_rules.py"]),
        ("Approval rules", COLLECTED_COUNTS["test_approval_rules.py"]),
        ("Pipeline integration", COLLECTED_COUNTS["test_pipeline_integration.py"]),
        ("Identity resolution", COLLECTED_COUNTS["test_identity_resolution.py"]),
        ("Discount negotiation", COLLECTED_COUNTS["test_discount_negotiation.py"]),
    ]
    labels = [label.replace(" ", "\n") for label, _ in ordered]
    values = [value for _, value in ordered]
    total = sum(values)

    fig, ax = plt.subplots(figsize=(9.2, 4.8), constrained_layout=True)
    colors = ["#0f766e", "#0ea5a4", "#14b8a6", "#2563eb", "#3b82f6", "#60a5fa"]
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel("Collected tests")
    ax.set_title(f"Selected Verification-Suite Coverage (total = {total})")
    ax.grid(axis="y", alpha=0.25)
    ax.set_ylim(0, max(values) + 10)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.8,
            str(value),
            ha="center",
            va="bottom",
            fontsize=10,
        )

    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    print(output_path)


if __name__ == "__main__":
    main()
