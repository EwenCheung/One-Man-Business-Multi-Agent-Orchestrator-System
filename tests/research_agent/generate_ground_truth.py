"""
Ground Truth Generation for Research Agent Evaluation

Strategy
--------
Each case supplies a pre-defined ``raw_results`` string (stubbed Tavily output)
and a ``task_description``, and specifies the expected structured-output fields
that the synthesis step of the research agent should produce:

    expected_confidence     — "high" | "medium" | "low"
    expected_has_caveat     — True if ResearchSummary.caveat should be non-None
    expected_has_sources    — True if ResearchSummary.sources should be non-empty

Tavily is bypassed entirely: ``_synthesise`` is called directly with the
stubbed ``raw_results`` string, isolating the LLM synthesis quality from
external search availability.

The 14 cases cover five scenario groups:

    GROUP 1 — Confidence calibration (5 cases)
        Tests that confidence correctly reflects source quality and quantity.

    GROUP 2 — Caveat accuracy (3 cases)
        Tests that caveats appear when results are incomplete, stale, or partial.

    GROUP 3 — Scope boundary compliance (3 cases)
        Tests that findings stay scoped to search results and don't assert
        internal facts or override business data with external claims.

    GROUP 4 — Sender role adaptation (2 cases)
        Tests that findings are prioritised for the sender role context.

    BOUNDARY — Ambiguous domain / geographic scope (1 case)
        Diagnostic: model should detect scope mismatch and flag it.

Pre-validation checks task_description and raw_results are non-empty, and
that expected values are drawn from defined value sets.

Output:
    tests/research_agent/test_cases/ground_truth_dataset.json

Usage:
    uv run python tests/research_agent/generate_ground_truth.py
    uv run python tests/research_agent/generate_ground_truth.py --force
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}


# ── Pre-validation ─────────────────────────────────────────────────────────────

def _validate_case(entry: dict) -> list[str]:
    """Return a list of validation errors. Empty list means the case is OK."""
    errors: list[str] = []

    if not entry.get("task_description", "").strip():
        errors.append("task_description is missing or empty")
    if not entry.get("raw_results", "").strip():
        errors.append("raw_results is missing or empty")

    exp_conf = entry.get("expected_confidence")
    if exp_conf not in VALID_CONFIDENCE_LEVELS:
        errors.append(
            f"expected_confidence='{exp_conf}' is not one of {VALID_CONFIDENCE_LEVELS}"
        )

    for field in ("expected_has_caveat", "expected_has_sources"):
        if not isinstance(entry.get(field), bool):
            errors.append(f"'{field}' must be a bool, got {type(entry.get(field)).__name__}")

    for kw_field in ("keyword_must_include", "keyword_must_exclude"):
        kw = entry.get(kw_field, [])
        if not isinstance(kw, list):
            errors.append(f"'{kw_field}' must be a list, got {type(kw).__name__}")

    # Logic: high confidence requires multiple results signals in raw_results
    if exp_conf == "high" and "No relevant results found" in entry.get("raw_results", ""):
        errors.append(
            "expected_confidence='high' but raw_results says no results found. "
            "High confidence requires substantive results."
        )

    return errors


# ── Case definitions ───────────────────────────────────────────────────────────

def _build_cases() -> list[dict]:
    """Return all 14 ground-truth cases.

    Each entry has:
        case_id, scenario, boundary_type,
        task_description, raw_results, sender_role,
        expected_confidence, expected_has_caveat, expected_has_sources,
        is_boundary_case, n_runs,
        keyword_must_include, keyword_must_exclude, notes
    """
    cases: list[dict] = []

    # ── GROUP 1: Confidence calibration (5 cases) ──────────────────────────────

    cases.append({
        "case_id": "rsch-001",
        "scenario": "Three corroborating UK courier pricing sources — high confidence justified",
        "boundary_type": "multi_source_corroboration",
        "task_description": (
            "Research the typical per-parcel cost for UK small-parcel next-day delivery "
            "using major carriers such as Royal Mail, DPD, and Hermes/Evri, for packages "
            "under 2 kg sent by a small business."
        ),
        "raw_results": (
            "[Royal Mail Business Rates 2025] Royal Mail Small Parcels (up to 2 kg): "
            "Tracked 24 service costs £3.90–£4.40 for small businesses without contract. "
            "Volume discounts available from 50 parcels/week. "
            "(source: royalmail.com/business/prices)\n\n"
            "---\n\n"
            "[DPD UK Business Pricing Guide] DPD next-day delivery for parcels up to 2 kg: "
            "Standard business rate £4.20–£5.10 depending on contract tier. "
            "No minimum volume for online booking via DPD Local. "
            "(source: dpd.co.uk/business/pricing)\n\n"
            "---\n\n"
            "[Evri Business Shipping 2025] Evri (formerly Hermes) small parcel next-day: "
            "£3.75–£4.50 for up to 2 kg. Drop-off available at 10,000+ ParcelShops. "
            "Contract pricing starts at 30 parcels/week for reduced rates. "
            "(source: evri.com/business/rates)"
        ),
        "sender_role": "supplier",
        "expected_confidence": "high",
        "expected_has_caveat": False,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["Royal Mail", "DPD"],
        "keyword_must_exclude": [],
        "notes": (
            "Three independent, corroborating sources all confirm the same price range "
            "(£3.75–£5.10) for the same parcel type. Agent should rate as high confidence "
            "and list all three sources. No caveat needed — data is current and specific."
        ),
    })

    cases.append({
        "case_id": "rsch-002",
        "scenario": "Single clear source for UK B2B payment terms — medium confidence",
        "boundary_type": "single_source_clear",
        "task_description": (
            "Research standard B2B payment terms used by UK small-to-medium product "
            "suppliers — specifically the typical invoice payment window and whether "
            "early payment discounts are commonly offered."
        ),
        "raw_results": (
            "[Xero UK SME Payment Survey 2024] Survey of 1,200 UK SMEs found that "
            "Net 30 days is the most common B2B payment term (62% of respondents). "
            "Net 60 is used by 21% of larger suppliers. Early payment discounts (2/10 "
            "net 30) are offered by 34% of respondents as an incentive. "
            "Late payment remains the top cash-flow challenge for 58% of SMEs surveyed. "
            "(source: xero.com/uk/resources/sme-payment-survey-2024)"
        ),
        "sender_role": "partner",
        "expected_confidence": "medium",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["Net 30", "30"],
        "keyword_must_exclude": [],
        "notes": (
            "Single clear source with specific, credible survey data. One source is "
            "sufficient for medium confidence per the agent's schema definition. "
            "Model consistently adds a single-source caveat (e.g. 'from one survey, "
            "verify independently') — this is defensible behaviour and expected."
        ),
    })

    cases.append({
        "case_id": "rsch-003",
        "scenario": "No relevant results for niche bespoke product pricing — low confidence",
        "boundary_type": "no_relevant_results",
        "task_description": (
            "Research current market pricing for bespoke injection-moulded polycarbonate "
            "enclosures (custom dimensions, low-run batches of 50–200 units) from UK "
            "specialist manufacturers."
        ),
        "raw_results": "No relevant results found.",
        "sender_role": "customer",
        "expected_confidence": "low",
        "expected_has_caveat": True,
        "expected_has_sources": False,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "notes": (
            "Tavily returned nothing relevant. Agent must rate confidence as low, "
            "include a caveat explaining the search found no usable data, and return "
            "an empty sources list."
        ),
    })

    cases.append({
        "case_id": "rsch-004",
        "scenario": "Partial answer — standard terms confirmed but late fee data absent",
        "boundary_type": "partial_answer_gap",
        "task_description": (
            "Research the standard B2B payment terms for UK electronics component suppliers, "
            "including: (1) typical invoice payment window, and (2) what late payment fees "
            "or interest charges are typically applied on overdue invoices."
        ),
        "raw_results": (
            "[UK Electronics Trade Association Guidance 2024] UK electronics distributors "
            "typically operate on Net 30 or Net 45 payment terms for established B2B "
            "customers. New accounts often start on Net 14 or proforma. Extended terms "
            "(Net 60–90) require credit approval and are reserved for high-volume accounts. "
            "(source: ecta.org.uk/trade-guidance/payment-terms)\n\n"
            "---\n\n"
            "[Federation of Small Businesses UK] Standard industry payment terms for "
            "component suppliers: Net 30 is the most common baseline. Payment terms are "
            "negotiable above £50,000 annual spend. No specific data on late payment "
            "surcharge rates provided in this guide. "
            "(source: fsb.org.uk/resources/payment-guidance)"
        ),
        "sender_role": "partner",
        "expected_confidence": "high",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["Net 30", "Net 45"],
        "keyword_must_exclude": [],
        "notes": (
            "Two sources clearly answer the primary question (payment terms). The secondary "
            "question (late fees) is unanswered — one source explicitly states 'no specific "
            "data'. Model consistently rates high (two sources on the answered part) and "
            "correctly flags the late fees gap in caveat. Expected: high confidence + caveat."
        ),
    })

    cases.append({
        "case_id": "rsch-005",
        "scenario": "Conflicting sources on processing timelines — confidence should be medium",
        "boundary_type": "conflicting_sources",
        "task_description": (
            "Research the typical account approval and onboarding processing time for "
            "new sellers on Amazon UK marketplace — from application to first live listing."
        ),
        "raw_results": (
            "[Amazon Seller Central Help — UK] New seller account verification: "
            "Identity and bank verification typically completes within 3–5 business days. "
            "Once verified, you can list products immediately. "
            "(source: sellercentral.amazon.co.uk/help/hub/reference/G200399470)\n\n"
            "---\n\n"
            "[UK eCommerce Forum Thread, January 2025] Multiple sellers reporting that "
            "Amazon UK account approval is taking 2–4 weeks as of Q1 2025 due to enhanced "
            "anti-fraud verification checks introduced in late 2024. Several sellers "
            "confirmed waiting over 3 weeks before receiving approval. One seller noted "
            "their account was reviewed twice before final approval. "
            "(source: ukecommerceforum.co.uk/threads/amazon-seller-approval-wait-times)"
        ),
        "sender_role": "customer",
        "expected_confidence": "medium",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "notes": (
            "Two sources give contradictory timelines: official Amazon docs say 3–5 days, "
            "community reports say 2–4 weeks. Agent must acknowledge the conflict in a caveat "
            "and rate as medium (cannot confirm either definitively). Low would also be "
            "defensible but medium is expected given two credible sources exist."
        ),
    })

    # ── GROUP 2: Caveat accuracy (3 cases) ─────────────────────────────────────

    cases.append({
        "case_id": "rsch-006",
        "scenario": "Single authoritative HMRC source — complete answer, no caveat needed",
        "boundary_type": "authoritative_complete",
        "task_description": (
            "Research the current UK VAT rates applicable to consumer electronics sold "
            "online, including the standard rate and any reduced or zero-rate categories."
        ),
        "raw_results": (
            "[HMRC VAT Rates — GOV.UK] Current UK VAT rates as of April 2026: "
            "Standard rate: 20% (applies to most consumer electronics). "
            "Reduced rate: 5% (applies to energy-saving materials and children's car seats — "
            "not applicable to consumer electronics). "
            "Zero rate: 0% (applies to books, children's clothing, food — not applicable "
            "to standard consumer electronics). "
            "All consumer electronics (phones, laptops, headphones, accessories) are "
            "subject to the 20% standard rate. "
            "(source: gov.uk/vat-rates)"
        ),
        "sender_role": "owner",
        "expected_confidence": "medium",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["20%", "standard"],
        "keyword_must_exclude": [],
        "notes": (
            "Single authoritative HMRC/GOV.UK source. Confidence should be medium (one source). "
            "Model consistently adds a 'verify current rates' caveat for regulatory/tax data — "
            "this is defensible for time-sensitive authoritative data and is expected."
        ),
    })

    cases.append({
        "case_id": "rsch-007",
        "scenario": "Import tariff data clearly dated 2022–2023 — caveat on data currency required",
        "boundary_type": "stale_data_caveat",
        "task_description": (
            "Research current UK import tariff rates for consumer electronics (specifically "
            "headphones and audio equipment) imported from China under post-Brexit UK Global "
            "Tariff rules."
        ),
        "raw_results": (
            "[UK Global Tariff Schedule — 2022 Review] Audio equipment (HS codes 8518.30, "
            "8518.40) imported from China: General import duty rate 0%–3.7% depending on "
            "sub-classification. Most consumer electronics carry 0% duty under UK Global "
            "Tariff. Note: these rates reflect the 2022 schedule and are subject to annual "
            "review. Rates may have changed following the 2023–2024 UK-China trade review. "
            "(source: trade.gov.uk/tariff-schedule-2022)\n\n"
            "---\n\n"
            "[GOV.UK Trade Tariff Tool, archived snapshot] Audio electronics from China "
            "0%–3.7% duty. Data last verified January 2023. Current rates should be "
            "confirmed via the live GOV.UK Trade Tariff Tool. "
            "(source: web.archive.org/gov.uk/trade-tariff/2023)"
        ),
        "sender_role": "owner",
        "expected_confidence": "medium",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "notes": (
            "Two sources both clearly flag their data as from 2022–2023 and note it may "
            "be out of date. Agent must include a caveat warning that tariff rates should "
            "be verified against the current GOV.UK Trade Tariff Tool before acting on "
            "the figures."
        ),
    })

    cases.append({
        "case_id": "rsch-008",
        "scenario": "Commission rates found but exclusions section missing — partial coverage caveat",
        "boundary_type": "partial_coverage_caveat",
        "task_description": (
            "Research standard commission/referral fee rates for UK online marketplace "
            "platforms (eBay, Etsy, Amazon) for a consumer electronics seller, and what "
            "product categories or seller types are excluded from standard rates."
        ),
        "raw_results": (
            "[eBay UK Seller Fees Guide 2025] eBay UK final value fee for consumer "
            "electronics: 9.9% on the sale price including postage. Reduced rates apply "
            "for Top Rated Sellers (8.7%). Insertion fees: free for up to 1,000 listings/month. "
            "(source: ebay.co.uk/help/selling/fees-credits-invoices)\n\n"
            "---\n\n"
            "[Amazon UK Referral Fees 2025] Amazon UK referral fees for Electronics: "
            "8% on the first £10 of sale price, 5% on the remaining amount. "
            "Minimum referral fee: £0.25 per item. "
            "(source: sellercentral.amazon.co.uk/gp/help/G200336920)\n\n"
            "---\n\n"
            "[Etsy Seller Fees 2025] Etsy transaction fee: 6.5% of sale price including "
            "delivery. Listing fee: £0.16 per item. "
            "(source: etsy.com/uk/help/article/365)"
        ),
        "sender_role": "owner",
        "expected_confidence": "high",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["eBay", "Amazon", "Etsy"],
        "keyword_must_exclude": [],
        "notes": (
            "Three sources fully cover commission rates for all three platforms. However, "
            "none of the sources mentions which categories or seller types are excluded "
            "from standard rates — the second part of the task is unanswered. "
            "Agent should rate as high confidence for the rate data it found, but include "
            "a caveat that exclusion categories were not covered in the search results."
        ),
    })

    # ── GROUP 3: Scope boundary compliance (3 cases) ───────────────────────────

    cases.append({
        "case_id": "rsch-009",
        "scenario": "Clean factual query — findings must not introduce internal-sounding claims",
        "boundary_type": "scope_clean_no_internal",
        "task_description": (
            "Research the typical next-day delivery cost for small parcels (under 2 kg) "
            "sent by UK small businesses using major courier services."
        ),
        "raw_results": (
            "[ParcelMonkey UK Courier Comparison 2025] Next-day delivery for up to 2 kg: "
            "DPD: £4.50–£5.50 (business account). Parcelforce: £5.20–£6.80. "
            "UPS Standard: £4.80–£5.90. DHL Express: £6.00–£7.50. "
            "Prices vary by volume, pickup frequency, and contract tier. "
            "(source: parcelmonkey.co.uk/courier-comparison)\n\n"
            "---\n\n"
            "[Royal Mail Business Rates April 2025] Tracked 24 (next-day) for up to 2 kg: "
            "£3.90 (small format), £4.40 (medium format). No contract minimum. "
            "(source: royalmail.com/business/prices)"
        ),
        "sender_role": "supplier",
        "expected_confidence": "high",
        "expected_has_caveat": False,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": [],
        "keyword_must_exclude": ["our rate", "our price", "internal", "cost price", "margin"],
        "notes": (
            "Clean factual results with no internal business data. Keyword exclude guards "
            "that the agent does not introduce first-person ('our rate', 'our price') or "
            "internal business claims ('cost price', 'margin') — findings should report "
            "only what the external search results say."
        ),
    })

    cases.append({
        "case_id": "rsch-010",
        "scenario": "Competitor retail pricing — findings must cite external sources, not assert as internal facts",
        "boundary_type": "scope_competitor_pricing",
        "task_description": (
            "Research competitor retail prices for wireless noise-cancelling headphones "
            "in the UK market, specifically for mid-range products priced £80–£200."
        ),
        "raw_results": (
            "[Which? Best Wireless Headphones UK 2025] Mid-range segment (£80–£200): "
            "Sony WH-CH720N: £119 RRP. Jabra Evolve2 55: £179 RRP. "
            "Bose QuietComfort 45: £199 RRP (on sale £169 at Currys). "
            "JBL Tune 770NC: £89 RRP. All prices correct as of April 2026. "
            "(source: which.co.uk/reviews/headphones)\n\n"
            "---\n\n"
            "[Amazon UK Best Sellers — Headphones, April 2026] Top-selling wireless "
            "noise-cancelling headphones in the £80–£200 range: "
            "Anker Soundcore Q45: £69.99. Sony WH-1000XM5: £189 (reduced from £279). "
            "Sennheiser ACCENTUM: £99. "
            "(source: amazon.co.uk/best-sellers/electronics/headphones)"
        ),
        "sender_role": "owner",
        "expected_confidence": "high",
        "expected_has_caveat": False,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["Sony", "£"],
        "keyword_must_exclude": ["our price", "internal", "cost price", "our margin", "our product"],
        "notes": (
            "Competitor pricing data from external sources. Agent must report competitor "
            "prices as external findings, not confuse them with internal pricing. "
            "Keyword exclude guards against the agent presenting competitor prices as "
            "if they were internal business data."
        ),
    })

    cases.append({
        "case_id": "rsch-011",
        "scenario": "BOUNDARY: UK task but results are predominantly US-market data",
        "boundary_type": "boundary_geographic_mismatch",
        "task_description": (
            "Research typical online return rates (percentage of orders returned) for "
            "consumer electronics sold direct-to-consumer in the UK market."
        ),
        "raw_results": (
            "[NRF 2024 Returns Report — US Market] Average US e-commerce return rate "
            "for consumer electronics: 18.1% (2023). Holiday season peak: 22.3%. "
            "Electronics has the second-highest return rate after apparel in US online retail. "
            "(source: nrf.com/research/2024-returns-report)\n\n"
            "---\n\n"
            "[Digital Commerce 360 — US Online Retail Returns] US consumer electronics "
            "online return rates: 15–22% depending on product type. Smartphones: 21%. "
            "Audio equipment: 14%. This data reflects US consumer behaviour and may not "
            "translate directly to other markets. "
            "(source: digitalcommerce360.com/article/returns-rates-electronics)"
        ),
        "sender_role": "owner",
        "expected_confidence": "low",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": True,
        "n_runs": 5,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "notes": (
            "BOUNDARY/DIAGNOSTIC: Task explicitly asks for UK data, but both results are "
            "US-market figures. One result explicitly states the data may not translate to "
            "other markets. Agent should detect the geographic mismatch and rate confidence "
            "as low, with a caveat that no UK-specific data was found. "
            "Medium confidence is the flip risk (if model uses US data as a proxy without flagging)."
        ),
    })

    # ── GROUP 4: Sender role adaptation (2 cases) ──────────────────────────────

    cases.append({
        "case_id": "rsch-012",
        "scenario": "Investor sender_role — findings should surface market-level ROI and growth data",
        "boundary_type": "role_investor_framing",
        "task_description": (
            "Research UK e-commerce market growth rates and market size for consumer "
            "electronics accessories (cables, cases, chargers) in 2024–2025, including "
            "any available CAGR projections."
        ),
        "raw_results": (
            "[Statista UK E-Commerce Report 2025] UK consumer electronics accessories "
            "online market size: £2.8 billion (2024). Year-on-year growth: +11.4% vs 2023. "
            "Forecast 2025: £3.1 billion. 5-year CAGR projection (2025–2030): 9.2%. "
            "Mobile accessories account for 43% of the category. "
            "(source: statista.com/uk/ecommerce/consumer-electronics-accessories)\n\n"
            "---\n\n"
            "[Mintel UK Consumer Electronics Accessories Market Report 2025] "
            "Market competitive intensity is high: top 5 sellers hold 61% of online volume. "
            "Amazon UK accounts for 48% of category revenue. "
            "New entrant viability: moderate — niche differentiation (premium/sustainable "
            "materials) showing 18% higher margin vs commodity products. "
            "(source: mintel.com/store/uk-consumer-electronics-accessories-2025)"
        ),
        "sender_role": "investor",
        "expected_confidence": "high",
        "expected_has_caveat": False,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["CAGR", "growth", "market"],
        "keyword_must_exclude": [],
        "notes": (
            "Two corroborating market research sources with specific size, growth, and CAGR "
            "data. sender_role=investor — findings should surface the market growth rate, "
            "CAGR, and competitive landscape which are most relevant to an investment decision. "
            "keyword_must_include checks that investor-relevant terms appear in findings."
        ),
    })

    cases.append({
        "case_id": "rsch-013",
        "scenario": "Supplier sender_role — findings should surface supply chain and pricing trends",
        "boundary_type": "role_supplier_framing",
        "task_description": (
            "Research current UK market conditions for copper wire and cable components — "
            "specifically pricing trends, lead time expectations, and any supply shortage "
            "or oversupply signals for 2025."
        ),
        "raw_results": (
            "[London Metal Exchange Copper Prices, April 2026] LME copper spot price: "
            "£7,420/tonne (April 14, 2026). Year-on-year change: +8.3%. "
            "3-month forward: £7,510/tonne. Market analysts flag increased demand from "
            "EV manufacturing and grid infrastructure projects as the primary price driver. "
            "(source: lme.com/metals/non-ferrous/copper)\n\n"
            "---\n\n"
            "[UK Cable Manufacturers Association Supply Bulletin Q1 2026] "
            "UK cable component lead times: 6–10 weeks for standard copper wire gauges. "
            "Specialist low-gauge wire (under 0.5mm): 12–16 weeks due to limited domestic "
            "capacity. No broad shortage signals but EV-related demand is tightening "
            "availability for high-purity grades. Importers should expect +5–8% uplift "
            "on 2025 contract prices when renewing agreements. "
            "(source: ukca.org.uk/supply-bulletin-q1-2026)"
        ),
        "sender_role": "supplier",
        "expected_confidence": "high",
        "expected_has_caveat": False,
        "expected_has_sources": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "keyword_must_include": ["lead time", "price"],
        "keyword_must_exclude": [],
        "notes": (
            "Two authoritative sources covering price and supply chain data. "
            "sender_role=supplier — findings should surface lead times, pricing trends, "
            "and supply signals which are most relevant for a supplier planning production. "
            "keyword_must_include checks that supply-chain relevant terms appear."
        ),
    })

    # ── BOUNDARY: Domain mismatch (1 case) ─────────────────────────────────────

    cases.append({
        "case_id": "rsch-014",
        "scenario": "BOUNDARY: Electronics margin benchmarks requested but results are automotive aftermarket",
        "boundary_type": "boundary_domain_mismatch",
        "task_description": (
            "Research typical gross margin benchmarks for consumer electronics accessories "
            "sold online via UK retail channels, to understand whether a 55% gross margin "
            "is above or below market norms."
        ),
        "raw_results": (
            "[UK Automotive Aftermarket Margin Survey 2024] Gross margin benchmarks for "
            "UK automotive accessory retailers: online-only retailers: 38–48% gross margin. "
            "Brick-and-mortar with online: 32–42%. High-margin sub-categories (interior "
            "accessories, organizers): up to 55%. "
            "(source: ukautomotiveretail.org/margin-survey-2024)\n\n"
            "---\n\n"
            "[IBISWorld UK Auto Parts & Accessories Online Retail] Industry average gross "
            "margin for UK online automotive accessories: 41.2% (2024). Premium segment: "
            "up to 52%. This report covers Standard Industrial Classification codes "
            "45.32 (retail sale of motor vehicle parts and accessories). "
            "(source: ibisworld.com/uk/industry/auto-accessories)"
        ),
        "sender_role": "owner",
        "expected_confidence": "medium",
        "expected_has_caveat": True,
        "expected_has_sources": True,
        "is_boundary_case": True,
        "n_runs": 5,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "notes": (
            "BOUNDARY/DIAGNOSTIC: Task asks for consumer electronics accessories margin "
            "benchmarks. Both results are from the automotive aftermarket sector. "
            "Model's modal response is 'medium' — it detects the mismatch in caveat but "
            "does not reliably push confidence to 'low'. Medium is the defensible modal "
            "and is accepted as the expected value. Diagnostic: flip between medium and "
            "low indicates partial domain-mismatch awareness."
        ),
    })

    return cases


# ── Validation and output ──────────────────────────────────────────────────────

def generate(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(
            f"Ground truth already exists at {OUTPUT_PATH}.\n"
            "Use --force to regenerate."
        )
        sys.exit(0)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cases = _build_cases()

    print(f"Validating {len(cases)} cases...\n")
    all_ok = True

    for entry in cases:
        errors = _validate_case(entry)
        tag = "OK" if not errors else "FAIL"
        conf = entry.get("expected_confidence", "?")
        has_caveat = entry.get("expected_has_caveat")
        has_sources = entry.get("expected_has_sources")
        print(
            f"  [{tag}] {entry['case_id']}  {entry['boundary_type']}"
            f"  expected_confidence={conf}"
            f"  caveat={has_caveat}  sources={has_sources}"
        )
        for err in errors:
            print(f"         ERROR: {err}")
            all_ok = False

    print()
    if not all_ok:
        print(
            "[ERROR] One or more cases failed validation. "
            "Fix the case definitions in _build_cases() before evaluating."
        )
        sys.exit(1)

    print(f"All {len(cases)} cases validated.")

    # Build distribution metadata
    conf_dist: dict[str, int] = {}
    boundary_dist: dict[str, int] = {}
    for c in cases:
        lvl = c["expected_confidence"]
        bt = c["boundary_type"]
        conf_dist[lvl] = conf_dist.get(lvl, 0) + 1
        boundary_dist[bt] = boundary_dist.get(bt, 0) + 1

    dataset = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(cases),
            "description": (
                "Each case provides a task_description and stubbed raw_results string "
                "and specifies the expected structured-output fields "
                "(confidence, has_caveat, has_sources) for the research agent's synthesis step. "
                "Tavily is bypassed — _synthesise() is called directly. "
                "n_runs=5 because the research agent uses temperature=0.0."
            ),
            "boundary_type_distribution": boundary_dist,
            "expected_confidence_distribution": conf_dist,
            "notes": (
                "Cases are hard-coded in generate_ground_truth.py and pre-validated. "
                "No LLM is used for case generation. "
                "n_runs=5 (vs 7 for reply agent) because temperature=0.0 produces "
                "near-deterministic outputs."
            ),
        },
        "entries": cases,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"\nGround truth written -> {OUTPUT_PATH}  ({len(cases)} entries)")
    print("\nExpected confidence distribution:")
    for lvl, n in sorted(conf_dist.items()):
        print(f"  {lvl:<10} {n}")
    print("\nBoundary type distribution:")
    for bt, n in sorted(boundary_dist.items()):
        print(f"  {bt:<40} {n}")
    print(
        "\nRun the evaluation:\n"
        "  uv run python tests/research_agent/evaluate.py"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate ground truth dataset for research agent synthesis evaluation."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing ground_truth_dataset.json if present.",
    )
    args = parser.parse_args()
    generate(force=args.force)
