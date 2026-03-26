---
name: stakeholder-framing
description: >
  Guides the research agent to prioritise and frame findings according to the
  sender's stakeholder role (customer, supplier, investor, partner, government).
  Affects both query angle selection and synthesis prioritisation.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - stakeholder
  - role-aware
  - prioritisation
---

# Stakeholder Framing

## Overview

The Reply Agent drafts a message for a specific stakeholder. Research findings
should already be prioritised and framed for that audience so the Reply Agent
can assemble a compelling, relevant response without re-sorting the data.

This skill affects **two phases**:

1. **Query extraction** — choose search angles that matter to this stakeholder.
2. **Synthesis** — order and frame findings by what this stakeholder cares about.

## Framing Rules by Role

### Customer (`customer`)

| Priority | What to surface                                                  | What to deprioritise |
| -------- | ---------------------------------------------------------------- | -------------------- |
| 1        | Facts that resolve the customer's specific complaint or question | Market-level figures |
| 2        | Delivery timelines, availability, service quality data           | Internal cost data   |
| 3        | Comparable offerings/alternatives if relevant                    | Industry trends      |

**Flag any finding that may raise or disappoint expectations** so the Reply Agent
can hedge appropriately.

### Supplier (`supplier`)

| Priority | What to surface                                                     | What to deprioritise                             |
| -------- | ------------------------------------------------------------------- | ------------------------------------------------ |
| 1        | External benchmarks: market pricing ranges, competitor supply terms | Internal cost structure                          |
| 2        | Industry payment norms, standard lead times                         | What we are willing to pay                       |
| 3        | Findings that support our negotiating position                      | High-demand signals that give suppliers leverage |

**Frame findings as leverage** — what is standard in the market that supports our
negotiating position. **Never surface** our internal margins, cost structure, or
willingness to pay.

### Investor (`investor`)

| Priority | What to surface                                         | What to deprioritise       |
| -------- | ------------------------------------------------------- | -------------------------- |
| 1        | Growth metrics: market size, YoY growth, TAM            | Operational minutiae       |
| 2        | CAC benchmarks, churn industry averages, unit economics | Individual customer issues |
| 3        | Analyst reports and industry data (over news articles)  | Anecdotal evidence         |

**Clearly distinguish actuals from projections** — investors will notice if these
are conflated. Frame every finding as evidence of market opportunity or
competitive moat.

### Partner (`partner`)

| Priority | What to surface                                                   | What to deprioritise                 |
| -------- | ----------------------------------------------------------------- | ------------------------------------ |
| 1        | Market positioning data: where does our joint offering sit?       | Internal disagreements               |
| 2        | Findings demonstrating mutual opportunity and strategic alignment | One-sided benefits                   |
| 3        | External validation of the market we operate in together          | Competitor weaknesses (keep neutral) |

### Government / Regulator (`government`)

| Priority | What to surface                                                   | What to deprioritise  |
| -------- | ----------------------------------------------------------------- | --------------------- |
| 1        | Official, primary-source regulatory data only                     | Industry opinion      |
| 2        | Jurisdiction, effective date, issuing authority for every finding | Informal commentary   |
| 3        | Exact wording from regulations where possible                     | Paraphrased summaries |

**Do not infer or paraphrase regulation** — quote exact wording where possible.
If ambiguous, flag explicitly rather than resolving.

### Unknown or Unrecognised Role

- Surface a balanced set of findings covering factual, market, and risk dimensions.
- Do not optimise the framing for any particular audience.
- The Reply Agent will handle tone adaptation.

## Quality Checklist

- [ ] Sender role identified from task context
- [ ] Findings ordered by priority for that role
- [ ] No internal/confidential data surfaced (especially for supplier/investor)
- [ ] Expectation-managing findings flagged where applicable
