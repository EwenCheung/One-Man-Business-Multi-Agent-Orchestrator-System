"""
Policy Document Generator

Sends a structured prompt to an LLM for each policy document, receives the generated
text, and writes it to a PDF in backend/policies/.

Usage:
    uv run python backend/db/generate_policies.py          # skip existing files
    uv run python backend/db/generate_policies.py --force  # regenerate all

The POLICY_SPECS list is the single source of truth for what gets generated.
Editing a spec and re-running with --force reproduces a new version of that document.
"""

import argparse
import sys
from pathlib import Path

from fpdf import FPDF
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.config import settings
from backend.db.policy_metadata import POLICY_SPECS as _BASE_SPECS

# ─── Output directory ────────────────────────────────────────────────────────

POLICIES_DIR = Path(__file__).parent / "policies"

# ─── Few-shot examples ───────────────────────────────────────────────────────

FEW_SHOT_EXAMPLES: list[dict] = [
    {
        "user": (
            "Write an Order Cancellation Policy for a one-man e-commerce business. "
            "The document must cover the following sections in order:\n\n"
            "1. Overview — purpose and scope\n"
            "2. Cancellation Window — orders may be cancelled within 2 hours of placement "
            "provided they have not yet been dispatched\n"
            "3. How to Cancel — the customer must contact support by email with their order number\n"
            "4. Refunds — full refund to the original payment method within 5 business days\n"
            "5. Exceptions — subscription orders and pre-order items cannot be cancelled\n\n"
            "Write approximately 300 words. Use formal language."
        ),
        "assistant": (
            "Order Cancellation Policy\n\n"
            "Overview\n\n"
            "This Order Cancellation Policy sets out the conditions under which customers may cancel "
            "an order placed through the business's online store. It applies to all orders made by "
            "individual consumers and business buyers alike. The business is committed to processing "
            "cancellations promptly and fairly, in accordance with applicable consumer protection law.\n\n"
            "Cancellation Window\n\n"
            "Customers may request the cancellation of an order within two hours of the time at which "
            "the order was placed, provided that the order has not yet been marked as dispatched. Once "
            "an order has entered the fulfilment process and a dispatch confirmation has been issued, "
            "it is no longer eligible for cancellation under this policy. In such cases, the customer "
            "may instead initiate a return in accordance with the Returns and Refunds Policy.\n\n"
            "How to Cancel\n\n"
            "To request a cancellation, the customer must contact the business by email at the address "
            "provided on the website, quoting their order number in the subject line. Cancellation "
            "requests submitted through any other channel cannot be guaranteed to be processed within "
            "the eligible window. The business will confirm whether the cancellation has been "
            "successfully applied within one hour of receiving the request during business hours.\n\n"
            "Refunds\n\n"
            "Where a cancellation is approved, the business will issue a full refund to the original "
            "payment method used at checkout. Refunds will be processed within five business days of "
            "the cancellation confirmation. The business does not charge any administrative fee for "
            "processing a cancellation within the permitted window.\n\n"
            "Exceptions\n\n"
            "The following order types are not eligible for cancellation under this policy: "
            "subscription-based orders, which are governed by the applicable subscription terms; and "
            "pre-order items, where cancellation rights are specified at the time of purchase. "
            "The business reserves the right to decline a cancellation request that does not meet "
            "the conditions set out in this policy."
        ),
    },
    {
        "user": (
            "Write a Customer Communication Policy for a one-man e-commerce business. "
            "The document must cover the following sections in order:\n\n"
            "1. Overview — purpose and who it applies to\n"
            "2. Response Times — email within 1 business day, social media within 4 hours during "
            "business hours\n"
            "3. Communication Channels — email is the official channel; social DMs are acknowledged "
            "but not binding\n"
            "4. Tone and Standards — professional, respectful, no informal language in written records\n"
            "5. Escalation — unresolved issues after 3 exchanges are escalated to a formal complaint\n\n"
            "Write approximately 300 words. Use formal language."
        ),
        "assistant": (
            "Customer Communication Policy\n\n"
            "Overview\n\n"
            "This Customer Communication Policy defines the standards by which the business engages "
            "with customers across all communication channels. It applies to all enquiries, complaints, "
            "and general correspondence initiated by customers or by the business. The purpose of this "
            "policy is to ensure that every interaction is handled consistently, professionally, and "
            "within agreed timeframes.\n\n"
            "Response Times\n\n"
            "The business commits to responding to all customer emails within one business day of "
            "receipt. For messages received after 17:00 or on weekends and public holidays, the "
            "response window begins at 09:00 on the next business day. Messages received via social "
            "media direct messaging will be acknowledged within four hours during business hours, "
            "though resolution may require the customer to follow up by email.\n\n"
            "Communication Channels\n\n"
            "Email is the official and preferred channel for all customer communications. Responses "
            "and commitments made by email constitute a written record and carry the full weight of "
            "the business's obligations. Acknowledgements made via social media direct messaging are "
            "informal in nature and do not create binding commitments unless subsequently confirmed "
            "in writing by email.\n\n"
            "Tone and Standards\n\n"
            "All written communications on behalf of the business must be professional, respectful, "
            "and free from informal or colloquial language. Staff and agents representing the business "
            "are expected to maintain a courteous tone regardless of the nature of the customer's "
            "enquiry or complaint.\n\n"
            "Escalation\n\n"
            "Where a customer issue has not been resolved after three exchanges within the same thread, "
            "the matter will be escalated to a formal complaint and handled in accordance with the "
            "business's Complaint Handling Procedure. The customer will be notified in writing when "
            "their case has been escalated."
        ),
    },
]

# ─── Policy specifications ───────────────────────────────────────────────────
# Each entry defines one PDF document.
#
# Fields:
#   filename        — output PDF name (also used as the document title)
#   category        — tag stored on every PolicyChunk from this document
#   hard_constraint — whether rules here are mandatory (vs. guidelines)
#   system_prompt   — sets the LLM's persona and formatting rules
#   user_prompt     — the actual instruction for this specific document

# Prompt-only specs — keyed by filename, merged with metadata from policy_metadata.py
_PROMPTS: dict[str, dict] = {
    "returns_policy.pdf": {
        "system_prompt": (
            "You are a legal and operations writer for a small e-commerce business. "
            "Write formal, precise policy documents that are enforceable and easy for "
            "customers and staff to understand. Use clear section headings. "
            "Do not use bullet points — write in full paragraphs."
        ),
        "user_prompt": (
            "Write a Returns and Refunds Policy for a one-man e-commerce business that sells "
            "physical products online. The document must cover the following sections in order:\n\n"
            "1. Overview — purpose of the policy and who it applies to\n"
            "2. Return Eligibility — the 30-day return window, condition requirements "
            "(unused, original packaging), and which product categories are excluded "
            "(digital goods, personalised items, opened consumables)\n"
            "3. How to Initiate a Return — step-by-step process the customer must follow, "
            "including contacting support and obtaining a return authorisation number\n"
            "4. Refund Processing — timeline (within 7 business days of receiving the return), "
            "method (original payment method only), and partial refund conditions\n"
            "5. Shipping Costs — who bears return shipping costs under different scenarios "
            "(customer fault vs. business fault)\n"
            "6. Exchanges — whether exchanges are offered and how they work\n"
            "7. Disputes — how unresolved disputes are escalated\n\n"
            "Write approximately 500 words. Use formal language."
        ),
    },
    "pricing_policy.pdf": {
        "system_prompt": (
            "You are a pricing and commercial policy writer for a small business. "
            "Write authoritative policy documents that set clear rules for pricing, "
            "discounts, and payment terms. Use clear section headings. Do not use bullet points — write in full paragraphs."
        ),
        "user_prompt": (
            "Write a Pricing and Discount Policy for a one-man e-commerce business. "
            "The document must cover the following sections in order:\n\n"
            "1. Overview — purpose of the policy\n"
            "2. Price Setting — how prices are determined (cost-plus margin), "
            "that listed prices are final and inclusive of applicable taxes\n"
            "3. Discount Authority — only the business owner may authorise discounts; "
            "no staff or agents may offer discounts without written approval\n"
            "4. Eligible Discount Scenarios — volume orders (10+ units get 5% off), "
            "loyalty customers (repeat buyers after 5 orders get 8% off), "
            "partner referrals (as defined in the partner agreement)\n"
            "5. Prohibited Discounts — no discounts on already-reduced items, "
            "no stacking of multiple discount types\n"
            "6. Payment Terms — B2C orders must be paid in full before dispatch; "
            "B2B invoices are net 30 days; late payment incurs 2% monthly interest\n"
            "7. Price Changes — the business reserves the right to change prices without notice; "
            "orders confirmed before a price change are honoured at the original price\n\n"
            "Write approximately 500 words. Use formal language."
        ),
    },
    "data_privacy_policy.pdf": {
        "system_prompt": (
            "You are a data protection and privacy policy writer. "
            "Write GDPR-aligned privacy policies for small businesses. "
            "Be precise about data categories, legal bases, and individual rights. "
            "Use clear section headings. Do not use bullet points — write in full paragraphs."
        ),
        "user_prompt": (
            "Write a Data Privacy Policy for a one-man e-commerce business operating in the EU/UK. "
            "The document must cover the following sections in order:\n\n"
            "1. Overview — who the data controller is, contact details, and scope\n"
            "2. Data Collected — personal data collected at checkout (name, email, address, phone), "
            "order history, communication logs, and website usage analytics\n"
            "3. Legal Basis — contract performance for order fulfilment; "
            "legitimate interest for fraud prevention; consent for marketing\n"
            "4. How Data Is Used — order processing, customer support, marketing (opt-in only), "
            "legal compliance\n"
            "5. Third-Party Sharing — data is shared only with: payment processors, "
            "shipping carriers, and cloud infrastructure providers; "
            "never sold to third parties\n"
            "6. Retention — order data retained for 7 years (tax compliance); "
            "marketing data deleted within 30 days of opt-out\n"
            "7. Individual Rights — right to access, rectification, erasure, portability, "
            "and objection; how to submit a request\n"
            "8. Data Breaches — notification within 72 hours to the relevant supervisory authority\n\n"
            "Write approximately 550 words. Use formal language."
        ),
    },
    "supplier_terms.pdf": {
        "system_prompt": (
            "You are a procurement and supplier relations policy writer for a small business. "
            "Write clear supplier engagement policies that protect the business while "
            "maintaining fair supplier relationships. Use clear section headings. Do not use bullet points — write in full paragraphs."
        ),
        "user_prompt": (
            "Write a Supplier Engagement Policy for a one-man e-commerce business. "
            "The document must cover the following sections in order:\n\n"
            "1. Overview — purpose of the policy and who it applies to\n"
            "2. Supplier Onboarding — required documents (business registration, bank details, "
            "product certificates), approval timeline (up to 14 days), and trial order requirement\n"
            "3. Pricing and Contracts — all pricing must be agreed in writing before any order; "
            "contracts are reviewed annually; price increases require 30 days written notice\n"
            "4. Payment Terms — standard payment is 30 days from invoice receipt; "
            "early payment discount of 2% if paid within 10 days\n"
            "5. Quality Standards — products must meet agreed specifications; "
            "defect rate above 2% triggers a formal review; "
            "the business reserves the right to reject and return non-conforming goods at supplier cost\n"
            "6. Lead Times — suppliers must commit to lead times in writing; "
            "failure to meet agreed lead times more than twice in a quarter triggers a review\n"
            "7. Termination — either party may terminate with 60 days written notice; "
            "immediate termination is permitted for material breach\n\n"
            "Write approximately 500 words. Use formal language."
        ),
    },
    "partner_agreement_policy.pdf": {
        "system_prompt": (
            "You are a commercial partnerships and agreements policy writer for a small business. "
            "Write clear partner relationship policies covering revenue sharing, IP, and conduct. "
            "Use clear section headings. Do not use bullet points — write in full paragraphs."
        ),
        "user_prompt": (
            "Write a Partner Agreement Policy for a one-man e-commerce business that works with "
            "referral and reseller partners. "
            "The document must cover the following sections in order:\n\n"
            "1. Overview — what constitutes a partner relationship and the purpose of this policy\n"
            "2. Partner Eligibility — partners must be registered businesses; "
            "individuals are not eligible; onboarding requires a signed agreement\n"
            "3. Revenue Share — referral partners receive 10% of the net order value for orders "
            "they directly generate; reseller partners negotiate individual rates set in their agreement; "
            "commissions are paid monthly in arrears\n"
            "4. Exclusivity — no exclusivity is granted by default; "
            "exclusive territory arrangements require a separate written addendum\n"
            "5. Intellectual Property — the business retains all IP; "
            "partners may use brand assets only within the bounds of the brand guidelines; "
            "no white-labelling without explicit written consent\n"
            "6. Reporting and Auditing — partners must provide monthly attribution reports; "
            "the business reserves the right to audit partner sales records with 14 days notice\n"
            "7. Termination — either party may terminate with 30 days written notice; "
            "accrued commissions are paid out within 45 days of termination\n\n"
            "Write approximately 500 words. Use formal language."
        ),
    },
}

# Merge metadata (filename, category, hard_constraint) with generation prompts
POLICY_SPECS: list[dict] = [
    {**base, **_PROMPTS[base["filename"]]}
    for base in _BASE_SPECS
]


# ─── PDF writer ──────────────────────────────────────────────────────────────

def _write_pdf(title: str, body: str, output_path: Path) -> None:
    """Render a plain-text policy document as a formatted PDF."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.multi_cell(0, 10, title, align="C")
    pdf.ln(6)

    # Body — detect section headings (lines that end with no period and are short)
    pdf.set_font("Helvetica", size=11)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue
        # Heuristic: heading if short, title-case or all-caps, no trailing period
        is_heading = (
            len(stripped) < 80
            and not stripped.endswith(".")
            and stripped[0].isupper()
            and stripped == stripped.title() or stripped.isupper()
        )
        if is_heading:
            pdf.ln(2)
            pdf.set_font("Helvetica", style="B", size=11)
            pdf.multi_cell(0, 7, stripped)
            pdf.set_font("Helvetica", size=11)
        else:
            pdf.multi_cell(0, 6, stripped)

    pdf.output(str(output_path))


# ─── LLM call ────────────────────────────────────────────────────────────────

def _generate_text(spec: dict, llm: ChatOpenAI) -> str:
    """Call the LLM with two few-shot examples followed by the spec's prompt."""
    messages = [SystemMessage(content=spec["system_prompt"])]

    for example in FEW_SHOT_EXAMPLES:
        messages.append(HumanMessage(content=example["user"]))
        messages.append(AIMessage(content=example["assistant"]))

    messages.append(HumanMessage(content=spec["user_prompt"]))

    response = llm.invoke(messages)
    return response.content.strip()


# ─── Main pipeline ───────────────────────────────────────────────────────────

def generate(force: bool = False) -> None:
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.0,  # deterministic for reproducibility
    )

    for spec in POLICY_SPECS:
        output_path = POLICIES_DIR / spec["filename"]

        if output_path.exists() and not force:
            print(f"  skipping {spec['filename']} (already exists, use --force to regenerate)")
            continue

        print(f"  generating {spec['filename']} ...")
        text = _generate_text(spec, llm)
        title = spec["filename"].replace("_", " ").replace(".pdf", "").title()
        _write_pdf(title, text, output_path)
        print(f"  saved → {output_path}")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate policy PDF documents via LLM.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all documents even if they already exist.",
    )
    args = parser.parse_args()
    generate(force=args.force)
