from pathlib import Path
import json
from typing import Any
from reportlab.lib import colors

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

from backend.data.policy_metadata import POLICY_SPECS

POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"

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
                "heading": "Refund and Shipping Rules",
                "content": [
                    "Refunds are processed within 5 to 7 business days after the returned item is inspected.",
                    "Original shipping charges are non-refundable unless the order was fulfilled incorrectly by the business.",
                    "Return shipping is paid by the customer unless the product arrived defective or the wrong item was shipped.",
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
        ],
    },
    "data_privacy_policy.pdf": {
        "title": "Data Privacy and Confidentiality Policy",
        "sections": [
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
                "heading": "Retention",
                "content": [
                    "Transaction and accounting records are retained for at least 7 years.",
                    "Inactive customer profiles may be archived after 24 months of inactivity.",
                    "Privacy requests and disclosure decisions must be logged for auditability.",
                ],
            },
        ],
    },
    "supplier_terms.pdf": {
        "title": "Supplier Terms and Procurement Standards",
        "sections": [
            {
                "heading": "Commercial Terms",
                "content": [
                    "Standard supplier payment terms are net 30 from invoice date unless a written supplier agreement states otherwise.",
                    "Minimum order quantities, lead times, and agreed supply prices must be documented in the active supplier agreement.",
                    "Staff must not promise accelerated payment, exclusivity, or revised commercial terms without owner approval.",
                ],
            },
            {
                "heading": "Quality and Delivery",
                "content": [
                    "Suppliers must meet the documented quality standards for the supplied product line.",
                    "Defect rates above the agreed threshold trigger review and may pause new orders pending owner decision.",
                    "Late delivery remedies may be discussed only in line with the written supplier agreement.",
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
                ],
            },
            {
                "heading": "Commercial Restrictions",
                "content": [
                    "Partners must not commit pricing, refund exceptions, delivery guarantees, or support promises beyond published terms.",
                    "Any request to revise commission percentage, exclusivity, or channel priority requires owner approval.",
                    "Partner-originated discount campaigns must be approved before launch.",
                ],
            },
            {
                "heading": "Termination and Review",
                "content": [
                    "Partner agreements are reviewed periodically according to the active agreement.",
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
        ],
    },
}


def generate_policy_pdf(filename: str, policy_data: dict[str, Any]):
    filepath = POLICIES_DIR / filename
    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
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

    story.append(Paragraph(policy_data["title"], title_style))
    story.append(Spacer(1, 0.2 * inch))

    for section in policy_data["sections"]:
        story.append(Paragraph(section["heading"], heading_style))
        story.append(Spacer(1, 0.1 * inch))
        for content in section["content"]:
            story.append(Paragraph(content, body_style))
            story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)
    print(f"Generated {filename}")


def generate_metadata_file():
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
    print("Generated policies_metadata.json")


def main():
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)
    expected_files = {spec["filename"] for spec in POLICY_SPECS}
    for stale_pdf in POLICIES_DIR.glob("*.pdf"):
        if stale_pdf.name not in expected_files:
            stale_pdf.unlink()
    for spec in POLICY_SPECS:
        filename = str(spec["filename"])
        generate_policy_pdf(filename, POLICY_CONTENT[filename])
    generate_metadata_file()
    print("Policy generation complete.")


if __name__ == "__main__":
    main()
