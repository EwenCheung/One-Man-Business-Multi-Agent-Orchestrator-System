---
name: synthesis
description: >
  Rules for structuring research findings into single-fact, attributed,
  non-extrapolated outputs that downstream agents can cite independently.
  Covers finding granularity, attribution, contradiction handling, and
  temporal integrity.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - findings
  - attribution
  - contradiction-handling
---

# Synthesis

## Overview

The research agent's output feeds directly into the Reply Agent, which must cite
individual claims in a customer-facing message. Every finding must therefore be
**singular, attributable, and honest about its limits**. This skill governs how
raw search results become structured findings.

## Rules

### 1. One fact per finding

Each entry in `key_findings` must be a single, concrete, attributable fact.
The Reply Agent needs to cite individual claims independently.

| ❌ BAD (bundled)                                                      | ✅ GOOD (singular)                                                         |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| "The TWS market grew 23% YoY and is projected to reach $45B by 2027." | "TWS market grew 23% YoY in 2025. (Source: IDC Q4 2025 report)"            |
|                                                                       | "TWS market projected to reach $45B by 2027. (Source: IDC Q4 2025 report)" |

### 2. Attribute every finding

Every fact must trace to a named source (URL or publication name).

- **Attributed:** "OEM TWS price range $8–12 per unit, 500 MOQ. (Source: Alibaba trade data, Jan 2026)"
- **Unattributed:** "OEM TWS earbuds typically cost $8–12." → Move to `caveat` if useful but unsourced.

Unattributed facts **must not** appear in `key_findings`.

### 3. Handle contradictions explicitly

When two sources report different figures for the same fact:

1. Include **BOTH** as separate findings, each with its source.
2. Add a caveat explaining the discrepancy (different methodologies, time periods, or market definitions).
3. **Never** resolve a contradiction by choosing one source arbitrarily.

**Example:**

```
key_findings:
  - "Global TWS market size: $38B in 2025. (Source: IDC Q4 2025)"
  - "Global TWS market size: $42B in 2025. (Source: Statista, Dec 2025)"

caveat: "IDC and Statista report different 2025 market sizes ($38B vs $42B),
likely due to different market boundary definitions (IDC excludes hearing aids)."
```

### 4. Caveat is not a default hedge — omit it when results are complete

`caveat` must be `None` (absent) unless you can name a **specific, identifiable**
problem with the results. Do not add a caveat as a general safety disclaimer.

**Set caveat to `None` when all of the following are true:**
- The results directly answer every part of the task
- Sources are current and from the correct domain/geography
- No contradictions exist between sources
- No part of the task was left unanswered

**Set caveat when at least one of these is true:**
- A part of the task was not answered by any result
- Sources are stale or flagged as potentially out of date
- Results are from the wrong domain or geography
- Two sources contradict each other
- Results are indirect or from low-trust sources

| ❌ BAD (hedge for safety)                                        | ✅ GOOD (specific gap)                                                     |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------- |
| "Results may not reflect all market conditions."                 | `None` — results are complete, current, and directly on-topic             |
| "Always verify with primary sources before acting."             | `None` — findings are already from primary sources                        |
| "Data currency cannot be guaranteed."                           | "Sources are dated 2022–2023; rates may have changed since then."         |

### 5. Do not extrapolate beyond the data

If sources report 2024 figures and the task asks about 2026, **do not**
project, interpolate, or estimate. Report what was found and note the gap.

| ❌ BAD                                                           | ✅ GOOD                                                          |
| ---------------------------------------------------------------- | ---------------------------------------------------------------- |
| "Market size is approximately $50B in 2026 based on 15% growth." | "Most recent market size: $38B (2025, IDC). No 2026 data found." |

Set `caveat`: "Only 2025 data available. 2026 figures require forward projection
which is outside this agent's scope."

## Output Format

Every synthesis must produce these fields:

| Field          | Type      | Description                                                   |
| -------------- | --------- | ------------------------------------------------------------- |
| `key_findings` | list[str] | One fact per item, each with inline source attribution        |
| `sources`      | list[str] | Deduplicated URLs or publication references                   |
| `confidence`   | str       | `high`, `medium`, or `low` (see confidence-calibration skill) |
| `caveat`       | str       | Gaps, contradictions, staleness, scope limitations            |

## Quality Checklist

Before returning findings, verify:

- [ ] Each finding contains exactly one fact
- [ ] Every finding has an inline source attribution
- [ ] Contradictions are reported as separate findings with a caveat
- [ ] No extrapolation or interpolation beyond found data
- [ ] `caveat` is `None` if results are complete, current, and on-topic — or contains a specific gap if not
- [ ] `sources` list matches the sources cited in findings
