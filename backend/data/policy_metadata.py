"""
Policy Metadata

Single source of truth for policy filenames, categories, and hard_constraint flags.
Imported by both the ingestion pipeline (backend) and the data generation script (data/).
"""

POLICY_SPECS: list[dict[str, object]] = [
    # hard_constraint=False — document contains sections where owner approval can unlock actions
    {"filename": "returns_policy.pdf", "category": "returns", "hard_constraint": False},
    {"filename": "pricing_policy.pdf", "category": "pricing", "hard_constraint": False},
    {"filename": "supplier_terms.pdf", "category": "supplier", "hard_constraint": False},
    {"filename": "partner_agreement_policy.pdf", "category": "partner", "hard_constraint": False},
    # hard_constraint=True — all rules are absolute, no approval path exists
    {"filename": "data_privacy_policy.pdf", "category": "data_privacy", "hard_constraint": True},
    {"filename": "owner_benefit_rules.pdf", "category": "owner_benefit", "hard_constraint": True},
]
