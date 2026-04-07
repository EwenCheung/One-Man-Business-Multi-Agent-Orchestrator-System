"""
Policy Document Generator

Expands structured key-point outlines via LLM into realistic multi-paragraph
policy text, then renders each document as a formatted PDF.

Flow:
    POLICY_CONTENT (key points) → LLM expansion → reportlab PDF → data/policies/

Usage:
    uv run python backend/data/generate_policies.py          # skip existing files
    uv run python backend/data/generate_policies.py --force  # regenerate all
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import settings
from backend.data.policy_metadata import POLICY_SPECS

# ─── Output directory ────────────────────────────────────────────────────────

POLICIES_DIR = Path(__file__).parent / "policies"

# ─── Policy specifications ───────────────────────────────────────────────────
# Each entry defines one PDF: its title, and the sections with key points that
# the LLM must expand into formal prose.

POLICY_CONTENT: dict[str, dict[str, Any]] = {
    "pricing_policy.pdf": {
        "title": "Pricing and Discount Policy",
        "sections": [
            {
                "heading": "Published Pricing",
                "content": [
                    "All products are sold using the published catalog price unless a documented exception applies.",
                    "Catalog pricing may be discussed with customers, but unpublished pricing authority must not be implied.",
                    "Cost price, gross margin, and negotiation room are confidential internal information.",
                ],
            },
            {
                "heading": "Standard Discount Bands",
                "content": [
                    "Orders of 10 to 49 units may receive up to a 10 percent volume discount.",
                    "Orders of 50 to 99 units may receive up to a 15 percent volume discount when stock is available.",
                    "Discounts cannot be stacked with loyalty, promotional, affiliate, or manual adjustments unless explicitly approved by the owner.",
                ],
            },
            {
                "heading": "Approval Rules",
                "content": [
                    "Any custom pricing, discount above the published band, or one-off commercial concession requires owner approval before it is promised.",
                    "No offer may be made below cost price under any circumstance.",
                    "Verbal pricing guidance is non-binding until written confirmation is issued.",
                ],
            },
            {
                "heading": "Payment Terms",
                "content": [
                    "Business-to-consumer orders must be paid in full before dispatch.",
                    "Business-to-business invoices are issued on net 30 day terms from invoice date.",
                    "Outstanding invoices accrue interest at 2 percent per month after the due date.",
                    "The business reserves the right to suspend supply to accounts with overdue balances.",
                ],
            },
            {
                "heading": "Price Changes",
                "content": [
                    "The business reserves the right to revise catalog prices without prior notice.",
                    "Orders confirmed in writing before a price change takes effect are honoured at the original price.",
                    "Promotional pricing is time-limited and does not create an ongoing entitlement for any customer.",
                ],
            },
        ],
    },
    "returns_policy.pdf": {
        "title": "Returns and Refunds Policy",
        "sections": [
            {
                "heading": "Standard Return Window",
                "content": [
                    "Unused products in original packaging may be returned within 30 days of delivery.",
                    "All accessories, inserts, and bundled items must be included for a standard return to be accepted.",
                    "Custom, special-order, clearance, and personalized items are not eligible for routine returns.",
                ],
            },
            {
                "heading": "How to Initiate a Return",
                "content": [
                    "Customers must contact support by email with their order number to request a return authorisation.",
                    "A return authorisation number must be obtained before sending any item back.",
                    "Items returned without a valid authorisation number may be refused or returned to the sender at their cost.",
                    "The business will confirm or decline the return request within two business days of receipt.",
                ],
            },
            {
                "heading": "Refund and Shipping Rules",
                "content": [
                    "Refunds are processed within 5 to 7 business days after the returned item is inspected.",
                    "Original shipping charges are non-refundable unless the order was fulfilled incorrectly by the business.",
                    "Return shipping is paid by the customer unless the product arrived defective or the wrong item was shipped.",
                    "Refunds are issued to the original payment method only.",
                ],
            },
            {
                "heading": "Exception Handling",
                "content": [
                    "A defective item reported within 90 days may qualify for replacement or full refund after evidence review.",
                    "Any goodwill refund, fee waiver, replacement outside policy, or special exception requires owner approval.",
                    "Customer-facing staff must not promise refunds outside documented conditions without owner approval.",
                ],
            },
            {
                "heading": "Exchanges",
                "content": [
                    "Exchanges are offered subject to stock availability and must be requested within the 30-day return window.",
                    "The customer is responsible for return shipping costs on exchange requests unless the original item was faulty.",
                    "Price differences on exchanges are charged or refunded to the original payment method.",
                ],
            },
        ],
    },
    "data_privacy_policy.pdf": {
        "title": "Data Privacy and Confidentiality Policy",
        "sections": [
            {
                "heading": "Overview and Scope",
                "content": [
                    "This policy governs how the business collects, uses, stores, and protects personal data.",
                    "It applies to all customer, supplier, partner, and investor data processed in the course of business operations.",
                    "The business acts as data controller and is responsible for compliance with applicable data protection law.",
                ],
            },
            {
                "heading": "Customer Information",
                "content": [
                    "Customer names, contact details, order history, and support records are stored only for business operations and service fulfillment.",
                    "Customer data is not sold or disclosed to third parties except where required for lawful processing or explicit consented service delivery.",
                    "Customers may request correction or deletion of eligible personal data subject to legal retention requirements.",
                ],
            },
            {
                "heading": "Confidential Business Data",
                "content": [
                    "Cost price, margin structure, supplier terms, negotiation strategy, and owner decision thresholds are confidential.",
                    "Confidential commercial information must not be disclosed to customers, partners, or suppliers unless expressly authorized by the owner.",
                    "Financial disclosure to investors requires the applicable NDA or owner-approved disclosure path.",
                ],
            },
            {
                "heading": "Legal Basis for Processing",
                "content": [
                    "Order fulfilment data is processed on the basis of contractual necessity.",
                    "Fraud prevention and business analytics rely on legitimate interest as the legal basis.",
                    "Marketing communications are sent only with explicit opt-in consent, which may be withdrawn at any time.",
                ],
            },
            {
                "heading": "Retention",
                "content": [
                    "Transaction and accounting records are retained for at least 7 years in line with tax compliance obligations.",
                    "Inactive customer profiles may be archived after 24 months of inactivity.",
                    "Marketing data is deleted within 30 days of an opt-out request.",
                    "Privacy requests and disclosure decisions must be logged for auditability.",
                ],
            },
            {
                "heading": "Individual Rights",
                "content": [
                    "Individuals have the right to access, correct, erase, and port their personal data.",
                    "Data subject requests must be acknowledged within 5 business days and fulfilled within 30 days.",
                    "In the event of a data breach affecting personal data, the relevant supervisory authority will be notified within 72 hours.",
                ],
            },
        ],
    },
    "supplier_terms.pdf": {
        "title": "Supplier Terms and Procurement Standards",
        "sections": [
            {
                "heading": "Supplier Onboarding",
                "content": [
                    "New suppliers must submit business registration documents, bank details, and product certificates before being approved.",
                    "Onboarding review takes up to 14 business days from receipt of complete documentation.",
                    "A trial order is required before a supplier is added to the active supply chain.",
                ],
            },
            {
                "heading": "Commercial Terms",
                "content": [
                    "Standard supplier payment terms are net 30 from invoice date unless a written supplier agreement states otherwise.",
                    "Minimum order quantities, lead times, and agreed supply prices must be documented in the active supplier agreement.",
                    "Staff must not promise accelerated payment, exclusivity, or revised commercial terms without owner approval.",
                    "An early payment discount of 2 percent applies if invoices are settled within 10 days of receipt.",
                ],
            },
            {
                "heading": "Quality and Delivery",
                "content": [
                    "Suppliers must meet the documented quality standards for the supplied product line.",
                    "Defect rates above the agreed threshold trigger review and may pause new orders pending owner decision.",
                    "Late delivery remedies may be discussed only in line with the written supplier agreement.",
                    "Failure to meet agreed lead times more than twice in a calendar quarter triggers a formal performance review.",
                ],
            },
            {
                "heading": "Disclosure Restrictions",
                "content": [
                    "Internal resale pricing, margin targets, and downstream customer negotiations must not be disclosed to suppliers.",
                    "Requests to change payment terms, volume commitments, or strategic sourcing allocations require owner approval.",
                    "Supply interruptions with material business impact must be escalated immediately.",
                ],
            },
            {
                "heading": "Termination",
                "content": [
                    "Either party may terminate the supplier relationship with 60 days written notice.",
                    "Immediate termination is permitted in the event of material breach, fraud, or wilful non-compliance.",
                    "Outstanding purchase orders at the time of termination will be fulfilled or cancelled according to the terms of the active agreement.",
                ],
            },
        ],
    },
    "partner_agreement_policy.pdf": {
        "title": "Partner Agreement and Channel Rules",
        "sections": [
            {
                "heading": "Partner Models",
                "content": [
                    "The business may operate affiliate, marketplace, referral, or revenue-share partner arrangements.",
                    "Commission or revenue-share percentages must follow the signed partner agreement for that relationship.",
                    "Partners may describe the business and products accurately but must not create unauthorized promises.",
                    "Only registered businesses are eligible for formal partner status; individuals are not eligible.",
                ],
            },
            {
                "heading": "Revenue Share",
                "content": [
                    "Referral partners receive 10 percent of the net order value for orders they directly generate.",
                    "Reseller partners negotiate individual rates documented in their signed agreement.",
                    "Commissions are calculated monthly and paid in arrears within 30 days of the period end.",
                    "No commission is payable on orders that are subsequently cancelled or fully refunded.",
                ],
            },
            {
                "heading": "Commercial Restrictions",
                "content": [
                    "Partners must not commit pricing, refund exceptions, delivery guarantees, or support promises beyond published terms.",
                    "Any request to revise commission percentage, exclusivity, or channel priority requires owner approval.",
                    "Partner-originated discount campaigns must be approved before launch.",
                    "No exclusivity is granted by default; exclusive territory arrangements require a separate written addendum.",
                ],
            },
            {
                "heading": "Intellectual Property",
                "content": [
                    "The business retains all intellectual property in its brand, products, and content.",
                    "Partners may use brand assets only within the bounds of the published brand guidelines.",
                    "White-labelling or rebranding of products requires explicit written consent from the owner.",
                ],
            },
            {
                "heading": "Termination and Review",
                "content": [
                    "Either party may terminate the partner agreement with 30 days written notice.",
                    "Accrued commissions at the time of termination are paid within 45 days of the termination date.",
                    "Termination, suspension, or commercial renegotiation must be handled according to the written agreement and owner direction.",
                    "Performance concerns that affect revenue or reputation should be escalated for owner review.",
                ],
            },
        ],
    },
    "owner_benefit_rules.pdf": {
        "title": "Owner Benefit and Approval Rules",
        "sections": [
            {
                "heading": "Core Objective",
                "content": [
                    "Every outbound reply should protect owner benefit, preserve margin, and avoid preventable downside.",
                    "A reply is risky if it reduces commercial leverage, creates owner loss, or adds liability without explicit owner approval.",
                    "When uncertain, the system should prefer a safe non-committal response or hold for owner approval.",
                ],
            },
            {
                "heading": "Automatic Hold Conditions",
                "content": [
                    "Hold any reply that offers a custom discount, waiver, free add-on, refund exception, or commercial concession outside written rules.",
                    "Hold any reply that reveals cost price, margin, internal negotiation room, supplier leverage, or owner decision thresholds.",
                    "Hold any reply that makes a guarantee, legal admission, exclusivity promise, or non-standard timeline commitment not grounded in retrieved evidence.",
                ],
            },
            {
                "heading": "Evidence Requirements",
                "content": [
                    "Factual claims about pricing, return eligibility, contract terms, commissions, lead times, and privacy handling must be grounded in retrieved records or policy excerpts.",
                    "If the system cannot ground a factual commercial claim, it must avoid stating it as fact.",
                    "Approval rules override convenience: protecting owner interest is more important than producing an instant answer.",
                ],
            },
            {
                "heading": "Escalation Protocol",
                "content": [
                    "Any communication that cannot be resolved within documented policy rules must be held for owner review before dispatch.",
                    "The owner must be notified of held replies within one business hour during operating hours.",
                    "Replies held for longer than 4 business hours without owner action should trigger a follow-up notification.",
                    "A record of every held reply and its outcome must be maintained for audit purposes.",
                ],
            },
            {
                "heading": "Prohibited Actions",
                "content": [
                    "No agent or automated system may commit to terms not documented in active policy without owner approval.",
                    "Representations about future pricing, product availability, or business direction are prohibited without owner sign-off.",
                    "Any communication that could constitute a legally binding offer must be reviewed by the owner before sending.",
                ],
            },
        ],
    },
}

# ─── LLM expansion ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a legal and operations writer for a small e-commerce business. "
    "Write formal, precise policy documents that are enforceable and clear. "
    "Use the exact section headings provided. "
    "Write in full paragraphs only — no bullet points, no numbered lists."
)


def _build_prompt(title: str, sections: list[dict]) -> str:
    lines = [
        f"Expand the following outline into a formal written policy document titled '{title}'.",
        "For each section, write 2 to 3 full paragraphs (~150 words) of formal business prose.",
        "Use the exact section heading before each section's text, prefixed with ##.",
        "Do not use bullet points or numbered lists.\n",
    ]
    for section in sections:
        lines.append(f"## {section['heading']}")
        for point in section["content"]:
            lines.append(f"- {point}")
        lines.append("")
    return "\n".join(lines)


def _expand_policy(
    title: str, sections: list[dict], llm: ChatOpenAI
) -> dict[str, str]:
    """Return {heading: expanded_text} for every section."""
    prompt = _build_prompt(title, sections)
    response = llm.invoke([SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)])
    text = response.content.strip()

    result: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            if current_heading is not None:
                result[current_heading] = "\n".join(current_lines).strip()
            current_heading = m.group(1).strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        result[current_heading] = "\n".join(current_lines).strip()

    return result


# ─── PDF rendering ───────────────────────────────────────────────────────────


def _write_pdf(
    title: str,
    sections: list[dict],
    expanded: dict[str, str],
    output_path: Path,
) -> None:
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.darkblue,
    )
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.2 * inch))

    for section in sections:
        heading = section["heading"]
        story.append(Paragraph(heading, heading_style))
        story.append(Spacer(1, 0.1 * inch))

        text = expanded.get(heading, "")
        for para in text.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para, body_style))
                story.append(Spacer(1, 0.1 * inch))

        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)


# ─── Metadata sidecar ────────────────────────────────────────────────────────


def _write_metadata() -> None:
    metadata_path = POLICIES_DIR / "policies_metadata.json"
    payload = {
        spec["filename"]: {
            "category": spec["category"],
            "hard_constraint": spec["hard_constraint"],
        }
        for spec in POLICY_SPECS
    }
    with open(metadata_path, "w") as f:
        json.dump(payload, f, indent=2)
    print("  wrote policies_metadata.json")


# ─── Main pipeline ───────────────────────────────────────────────────────────


def generate(force: bool = False) -> None:
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)

    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
    )

    for filename, policy_data in POLICY_CONTENT.items():
        output_path = POLICIES_DIR / filename

        if output_path.exists() and not force:
            print(f"  skipping {filename} (already exists — use --force to regenerate)")
            continue

        print(f"  generating {filename} ...")
        expanded = _expand_policy(policy_data["title"], policy_data["sections"], llm)
        _write_pdf(policy_data["title"], policy_data["sections"], expanded, output_path)
        print(f"  saved → {output_path}")

    _write_metadata()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate policy PDFs via LLM expansion.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all documents even if they already exist.",
    )
    args = parser.parse_args()
    generate(force=args.force)
