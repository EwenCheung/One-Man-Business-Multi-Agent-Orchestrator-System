---
name: source-evaluation
description: >
  Provides a trust hierarchy for ranking web sources by credibility, recency,
  and authority. Ensures research findings are grounded in reliable, timely data
  and that primary sources are preferred over secondary reports.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - credibility
  - trust-hierarchy
  - source-ranking
---

# Source Evaluation

## Overview

Not all search results are equal. This skill defines how to rank, filter, and
assess every source encountered during web search so that only credible,
attributable data enters the findings.

## Trust Hierarchy

Apply this hierarchy when deciding which sources to include and how to weight them:

| Tier | Source Type                                      | Trust Level | Notes                                           |
| ---- | ------------------------------------------------ | ----------- | ----------------------------------------------- |
| 1    | Industry analyst report (Gartner, IDC, Statista) | High        | Gold standard for market data                   |
| 1    | Government or regulatory body publication        | High        | Authoritative for compliance/legal              |
| 1    | Company official press release or IR page        | High        | Reliable for company-specific facts             |
| 2    | Established trade publication or news outlet     | Medium-High | Good for trends; verify figures against primary |
| 3    | General news aggregator                          | Medium      | Acceptable for context; not for key figures     |
| 4    | Blog, forum, review site                         | Low         | Corroborate before using in findings            |

**When two sources conflict, prefer the higher-tier source.** If both are same
tier, include both as separate findings and note the discrepancy in caveat.

## Recency Rules

Business intelligence has a short shelf life. Apply these recency thresholds:

| Data Type                          | Stale After          | Action When Stale                   |
| ---------------------------------- | -------------------- | ----------------------------------- |
| Market pricing, supply chain costs | 6 months             | Note date; set confidence ≤ medium  |
| Market size, growth rates          | 18 months            | Note date; set confidence ≤ medium  |
| Regulatory requirements            | Check effective date | Note if amendment is pending        |
| Company announcements              | 12 months            | Acceptable if no newer data         |
| Competitive positioning            | 6 months             | Fast-moving markets; flag staleness |

**Always note the publication date** in every finding so downstream agents can
assess relevance.

## Primary vs Secondary Sources

| Prefer                  | Over                             |
| ----------------------- | -------------------------------- |
| IDC report figure       | News article citing IDC report   |
| Government gazette text | Blog post summarising regulation |
| Company IR filing       | Analyst commentary about filing  |

If a secondary source cites a primary, and you can retrieve the original figure,
use the primary and cite it directly. If the primary is behind a paywall, cite
the secondary but note "as reported by [secondary source]."

## Quality Checklist

For each source included in findings, verify:

- [ ] Source type identified and trust tier assigned
- [ ] Publication date noted (or flagged as unknown)
- [ ] Recency threshold checked for the data type
- [ ] Primary source preferred where available
- [ ] URL or publication name recorded for attribution
