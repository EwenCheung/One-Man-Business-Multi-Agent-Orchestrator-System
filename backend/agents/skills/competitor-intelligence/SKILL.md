---
name: competitor-intelligence
description: >
  Discipline for researching competitor products, pricing, and strategy.
  Covers source hierarchy by data type, the no-recommendation rule, handling
  incomplete or stale data, and multi-competitor reporting structure.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - competitors
  - market-positioning
  - product-comparison
---

# Competitor Intelligence

## Overview

Competitor research requires specific rigour to avoid misleading the business.
The research agent surfaces **observable facts** about competitors — it never
assesses whether our product is better or worse. That judgement belongs to the
Reply Agent and the founder.

## What to Look For

For each competitor mentioned in the task, prioritise findings in this order:

| Priority | Category                       | Examples                                                                    |
| -------- | ------------------------------ | --------------------------------------------------------------------------- |
| 1        | Product specs and capabilities | Features, performance benchmarks, supported platforms                       |
| 2        | Pricing and commercial terms   | Unit price, subscription tiers, MOQ, contract length                        |
| 3        | Recent strategic moves         | Launches, partnerships, funding rounds, regulatory filings                  |
| 4        | Customer sentiment             | Aggregate reviews, NPS data, public complaints (reputable aggregators only) |
| 5        | Market positioning             | How the competitor describes itself vs how the market perceives it          |

## Source Discipline by Data Type

Different competitor facts require different source types. Apply the trust
hierarchy from the source-evaluation skill, with these additions:

| Source                                      | Useful For                        | Caution                                      |
| ------------------------------------------- | --------------------------------- | -------------------------------------------- |
| Competitor's own website / press release    | Specs, launch dates, pricing page | Treat positioning claims as self-promotional |
| Independent analyst report                  | Market share, positioning         | Preferred for competitive landscape          |
| Tech/trade review (TechCrunch, The Verge)   | Specs, first impressions          | Check publication date carefully             |
| Customer review aggregator (G2, Trustpilot) | Sentiment, common complaints      | Not for specs or pricing                     |
| Job postings                                | Strategic direction hints         | Speculative — note in caveat                 |

## The No-Recommendation Rule

This agent surfaces facts. It does **NOT** assess competitive positioning.

| ❌ NEVER                                   | ✅ ALWAYS                                                                        |
| ------------------------------------------ | -------------------------------------------------------------------------------- |
| "Competitor X is inferior because..."      | "Competitor X advertises 4-hour battery life. (Source: product page, Mar 2026)"  |
| "Our product is better than Y in..."       | "Competitor Y charges $15/unit at 1000 MOQ. (Source: Alibaba listing, Feb 2026)" |
| "We recommend focusing on Z's weakness..." | Report the observable fact; let the Reply Agent draw conclusions                 |

## Handling Incomplete Competitor Data

Competitor data is often incomplete or strategically withheld. Apply these rules:

| Situation                                      | Action                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| Specs only from competitor's own materials     | Label the source clearly in the finding                             |
| Pricing not publicly listed                    | Note explicitly: "Pricing not publicly available" — do not estimate |
| Data is > 6 months old in a fast-moving market | Note staleness in caveat; set confidence ≤ medium                   |
| Only rumour-site data on unreleased features   | Do not include — note in caveat that no confirmed data exists       |

## Multiple Competitors

When the task asks about multiple competitors:

- Report each competitor as a **separate finding block**
- Do not combine or average data across competitors
- Preserve individual attribution per competitor
- If the task asks for a comparison table, structure findings so the Reply Agent
  can construct one, but do not draw comparative conclusions yourself

## Quality Checklist

- [ ] Each finding states an observable fact, not a judgement
- [ ] Source type appropriate for the data type (see table above)
- [ ] No recommendations or competitive assessments
- [ ] Incomplete data explicitly noted (not silently omitted)
- [ ] Multiple competitors reported separately
- [ ] Publication date checked and staleness flagged if applicable
