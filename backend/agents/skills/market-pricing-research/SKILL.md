---
name: market-pricing-research
description: >
  Rules for handling pricing data — distinguishing price types, anchoring to
  context (date, region, volume, currency), and separating projections from
  actuals. Prevents common pricing-data errors that mislead business decisions.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - pricing
  - market-data
  - financial-benchmarks
---

# Market Pricing Research

## Overview

Pricing data has specific failure modes that can mislead business decisions.
Conflating wholesale with retail, omitting currency, or presenting a forecast as
a current fact can cause the founder to negotiate from a wrong baseline. Apply
these rules whenever a task involves prices, costs, or financial benchmarks.

## Rules

### 1. Always distinguish price types

Never report a price without specifying its type. Conflating these is a critical
error:

| Type                  | Definition                                                   |
| --------------------- | ------------------------------------------------------------ |
| Wholesale / OEM price | Unit cost from manufacturer or distributor to business buyer |
| Retail / RRP price    | End-consumer price on open market                            |
| Contract price        | Negotiated price under an existing agreement                 |
| Spot price            | Current open-market price without a contract                 |
| List price            | Published price before discounts                             |

**Always state which type you found.** If unclear from the source, label it as
`type unspecified` and note the ambiguity in caveat.

### 2. Always anchor price data to context

Every price finding **must** include all of the following. If any is missing, note
it in caveat:

| Required Field      | Why                                                                        |
| ------------------- | -------------------------------------------------------------------------- |
| **Date**            | Pricing changes; state when the figure was published or effective          |
| **Region / Market** | Prices vary significantly by geography                                     |
| **Volume tier**     | Wholesale pricing is almost always volume-dependent; note MOQ if available |
| **Currency**        | Never omit currency, especially for cross-border supply chains             |

**Example of a well-formed finding:**

> "OEM unit price for TWS earbuds (500+ MOQ): USD $8–12, Southeast Asia
> suppliers, Q1 2026. (Source: Alibaba trade data, verified Jan 2026)"

### 3. Projections vs actuals

Never present a projected or forecast figure as a current fact.

| ❌ BAD                  | ✅ GOOD                                                                                 |
| ----------------------- | --------------------------------------------------------------------------------------- |
| "Market price is $45B." | "Market projected to reach $45B by 2027 according to IDC forecast (published Q4 2025)." |

If only forecast data is available and the task requires current data, set
confidence to `medium` or `low` and note the gap in caveat.

### 4. Price ranges vs point estimates

Prices sourced from web search are rarely single figures — they are ranges.
Always report the range, not just the midpoint or most favourable end:

| ❌ BAD                   | ✅ GOOD                                                                |
| ------------------------ | ---------------------------------------------------------------------- |
| "Wholesale price is $8." | "Wholesale price range: $8–15 per unit (500 MOQ), varies by supplier." |

### 5. Competitor pricing caveats

When researching what competitors charge:

- Distinguish publicly listed price from actual transaction price (discounts are common)
- Note whether the price was found on the competitor's own site (potentially strategic positioning) vs an independent aggregator
- Flag if the competitor's pricing model differs (e.g. subscription vs one-off) — incompatible models must not be directly compared

## Quality Checklist

For each price finding, verify:

- [ ] Price type explicitly stated (wholesale, retail, spot, etc.)
- [ ] Date of the pricing data included
- [ ] Region/market specified
- [ ] Currency stated
- [ ] Volume tier or MOQ noted (if wholesale)
- [ ] Projections clearly labelled as such, not presented as actuals
- [ ] Ranges reported, not just point estimates
