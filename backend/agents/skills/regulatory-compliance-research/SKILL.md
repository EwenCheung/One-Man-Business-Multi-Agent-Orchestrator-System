---
name: regulatory-compliance-research
description: >
  High-accuracy rules for researching laws, regulations, and licensing.
  Mandates primary sources only, requires specific citation fields (jurisdiction,
  authority, effective date, citation, URL), defines escalation signals for the
  Risk Node, and enforces the boundary between finding facts and giving legal advice.
version: 1.0.0
author: system
applies-to:
  - research-agent
tags:
  - regulatory
  - compliance
  - legal
  - government
---

# Regulatory Compliance Research

## Overview

Regulatory research has a higher accuracy bar than market research. Errors here
can expose the business to legal or reputational risk. This skill applies
whenever a task involves laws, regulations, licensing, or government
requirements.

## Rules

### 1. Primary sources only

Regulatory findings **must** trace to official, primary sources:

| ✅ Acceptable                      | Examples                                                   |
| ---------------------------------- | ---------------------------------------------------------- |
| Government legislative databases   | legislation.gov.uk, eur-lex.europa.eu, federalregister.gov |
| Regulatory body official sites     | FCA, FDA, MAS, ACRA, GDPR supervisory authorities          |
| Official government press releases | Ministerial announcements, gazette notices                 |

| ❌ Never use as primary citation | Why                                     |
| -------------------------------- | --------------------------------------- |
| News articles                    | May paraphrase incorrectly              |
| Legal blogs or commentary        | Opinion, not law                        |
| Wikipedia                        | Not authoritative for regulatory claims |

If **no primary source is found**, set confidence to `low` and state explicitly:
"Official verification required — no primary source located."

### 2. Mandatory fields for every regulatory finding

Every regulatory finding **must** include all of the following. If any field is
missing, note it in caveat:

| Field                 | Description                                                       |
| --------------------- | ----------------------------------------------------------------- |
| **Jurisdiction**      | Which country / state / region does this apply to?                |
| **Issuing authority** | Which body enacted or enforces this rule?                         |
| **Effective date**    | When did it come into force? Is it current, pending, or repealed? |
| **Exact citation**    | Act name, section number, or regulation reference                 |
| **Source URL**        | Direct link to the official text                                  |

**Example of a well-formed regulatory finding:**

> "Businesses must register for GST if annual taxable turnover exceeds SGD 1
> million. Jurisdiction: Singapore. Authority: IRAS. Effective: 1 Jan 2023.
> Citation: GST Act (Cap. 117A), s.8. Source: iras.gov.sg"

### 3. Never resolve ambiguity

If a regulation is ambiguous, jurisdiction is unclear, or the rule appears to
have exceptions:

1. Report **both interpretations** as separate findings.
2. Do **NOT** choose one interpretation.
3. Note the conflict in caveat.
4. Add: "Recommend that the founder seek qualified legal advice."

### 4. Escalation signals

Flag any of the following **immediately** in caveat so the Orchestrator can route
to the Risk Node:

| Signal                                            | Example                                  |
| ------------------------------------------------- | ---------------------------------------- |
| Potential regulatory breach or liability          | Task reveals possible non-compliance     |
| Requirements differ across relevant jurisdictions | Singapore vs Malaysia tax rules conflict |
| Regulation changed within last 12 months          | New amendment effective Jan 2026         |
| No definitive answer from a primary source        | Ambiguous statute, no clear guidance     |

Use explicit language: "⚠ ESCALATION: [reason]. Recommend routing to Risk Node."

## Scope Boundary

This agent finds and reports regulatory facts. It does **NOT**:

| Action                                      | Owner                                      |
| ------------------------------------------- | ------------------------------------------ |
| Advise on whether the business is compliant | Legal counsel                              |
| Interpret ambiguous statutes                | Legal counsel                              |
| Recommend legal strategy                    | Founder / Legal counsel                    |
| Substitute for qualified legal advice       | N/A — always recommend professional review |

## Quality Checklist

For each regulatory finding, verify:

- [ ] Sourced from an official, primary authority
- [ ] All 5 mandatory fields present (jurisdiction, authority, date, citation, URL)
- [ ] No paraphrased regulation — exact wording where possible
- [ ] Ambiguities reported as multiple findings, not resolved
- [ ] Escalation signals flagged with explicit ⚠ marker
- [ ] Caveat includes "seek qualified legal advice" where uncertainty exists
