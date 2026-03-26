---
name: confidence-calibration
description: >
  Strict criteria for assigning high/medium/low confidence levels to research
  findings based on source count, credibility, and recency. Defines behaviour
  when confidence is low to ensure honest reporting of uncertainty.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - confidence
  - quality-control
  - uncertainty
---

# Confidence Calibration

## Overview

The `confidence` field in the research output is consumed by the Reply Agent to
decide how assertively to present information. Inflated confidence causes the
business to act on unreliable data; deflated confidence creates unnecessary
hedging. This skill defines exactly when each level applies.

## Confidence Levels

| Level    | Criteria                                                                                                   | Example                                              |
| -------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `high`   | ≥ 2 independent, credible sources corroborate the same specific fact                                       | IDC and Statista both report TWS market grew 23% YoY |
| `medium` | 1 clear, credible, primary source supports the finding                                                     | Single IDC report with a specific figure             |
| `low`    | Results are indirect, outdated (stale per source-evaluation thresholds), from low-trust sources, or absent | Only a 2023 blog post mentioning the topic           |

### Decision Tree

```
Found ≥ 2 independent credible sources agreeing? → high
Found 1 credible primary source? → medium
Found only secondary/low-trust/stale/no sources? → low
```

## Behaviour When Confidence Is Low

Low confidence does NOT mean "return nothing." Follow these steps:

1. **Still populate `key_findings`** with what was found, clearly marked as uncertain.
   - Example: "TWS earbuds OEM price range estimated $6–15 (single source, SEO blog, 2023 — treat as approximate)."
2. **Explain the gap precisely in `caveat`** so the Reply Agent can communicate it
   honestly.
   - Example: "Only one low-trust source found; data is from 2023 and may not
     reflect current pricing. Recommend verifying with a supplier quote."
3. **Never leave `key_findings` empty without explanation.** If absolutely nothing
   was found, add a finding like: "No relevant data found via web search for
   [topic]." and explain in caveat what was searched and why it failed.

## Anti-patterns

| ❌ Don't                                           | ✅ Do                                         |
| -------------------------------------------------- | --------------------------------------------- |
| Set `high` because one very detailed source exists | Set `medium` — detail ≠ corroboration         |
| Set `low` without explaining what's missing        | Always pair with a specific caveat            |
| Leave `key_findings` empty and set `low`           | Still report what was found, even if weak     |
| Set `high` for projections/forecasts               | Forecasts are ≤ `medium` even if sourced well |
