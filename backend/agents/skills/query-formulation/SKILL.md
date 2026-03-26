---
name: query-formulation
description: >
  Teaches the research agent to construct keyword-style search queries that
  maximise retrieval of authoritative, specific results from web search engines.
  Covers query structure, angle coverage, source targeting, and data-leak prevention.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - search
  - query-design
  - information-retrieval
---

# Query Formulation

## Overview

The research agent's only external data source is web search (Tavily). Query
quality is the single largest lever on result quality: a vague query returns
noise, a precise query returns facts. This skill defines how to formulate every
search query.

## Rules

### 1. Use keyword-style queries, not questions

The search engine ranks by keyword relevance, not intent comprehension. Strip
filler words and structure queries as keyword phrases.

| ❌ BAD                                                                 | ✅ GOOD                                               |
| ---------------------------------------------------------------------- | ----------------------------------------------------- |
| "what is the current wholesale price of TWS earbuds in Southeast Asia" | "TWS earbuds OEM wholesale price Southeast Asia 2026" |
| "how much does it cost to register a company in Singapore"             | "Singapore company registration cost ACRA 2026"       |

### 2. Cover different angles with each query

Each query must address a **distinct facet** of the task — not paraphrase the
same question. Prioritise:

1. **Primary fact** — the most important data point the task requires (run first).
2. **Corroborating angle** — a complementary search targeting a different source type, region, or dimension.

**Example for task "find OEM pricing for TWS earbuds":**

| Query # | Purpose             | Query                                                  |
| ------- | ------------------- | ------------------------------------------------------ |
| 1       | Primary fact        | `TWS earbuds OEM wholesale price Southeast Asia 2026`  |
| 2       | Corroborating angle | `TWS earbuds supplier unit cost Alibaba MOQ 2025 2026` |

### 3. Target authoritative source types

| Prefer                                            | Avoid                        |
| ------------------------------------------------- | ---------------------------- |
| Industry analyst reports (Gartner, IDC, Statista) | Forums, Q&A sites            |
| Company press releases, IR filings                | Review aggregators           |
| Trade publications (e.g. Nikkei Asia, TechInAsia) | SEO content farms            |
| Regulatory body publications                      | Blog posts without citations |
| Reputable news outlets                            | Social media threads         |

### 4. Never include sensitive internal data in queries

Queries leave the system boundary and hit an external API. Never embed:

- Internal pricing margins or cost structures
- Contract terms or negotiation positions
- Customer names, order details, or revenue figures
- Profit targets or financial projections

## Quality Checklist

Before finalising queries, verify each one passes:

- [ ] Keyword-style, not a natural language question
- [ ] Contains a date anchor (year or quarter) for time-sensitive data
- [ ] Targets a different angle from every other query in the batch
- [ ] Contains zero internal/confidential data
- [ ] Would plausibly return results from an authoritative source type
