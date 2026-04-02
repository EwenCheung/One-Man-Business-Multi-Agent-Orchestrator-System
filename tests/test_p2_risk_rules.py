"""
test_p2_risk_rules.py — Unit tests for the P2 risk rule checkers.

Tests:
  - check_pii_leakage():      credit cards, SSNs, API keys, passwords, IBAN
  - check_role_sensitivity(): customer, investor, partner role-specific risks
  - aggregate_risk():         PII → HIGH, role risk → MEDIUM
"""

import pytest

from backend.nodes.risk_rules import (
    check_pii_leakage,
    check_role_sensitivity,
    aggregate_risk,
)


# ── PII Checks ──────────────────────────────────────────────────────────────


def test_credit_card_detected():
    flags = check_pii_leakage("Your card 4111111111111111 has been charged.")
    assert any("Credit card" in f for f in flags)


def test_ssn_detected():
    flags = check_pii_leakage("Your SSN is 123-45-6789 per our records.")
    assert any("SSN" in f for f in flags)


def test_api_key_detected():
    flags = check_pii_leakage("Auth with sk-abcdefghijklmnopqrstuvwxyz1234 to call the API.")
    assert any("API/Secret" in f for f in flags)


def test_password_detected():
    flags = check_pii_leakage("password:mysecret123 has been reset.")
    assert any("Password" in f for f in flags)


def test_iban_detected():
    flags = check_pii_leakage("Your IBAN is GB29NWBK60161331926819 for bank transfers.")
    assert any("IBAN" in f for f in flags)


def test_clean_reply_has_no_pii_flags():
    flags = check_pii_leakage("Thank you for your order! We will ship within 3 days.")
    assert flags == []


# ── Role Sensitivity Checks ─────────────────────────────────────────────────


def test_supplier_name_exposed_to_customer():
    flags = check_role_sensitivity(
        "We source from our supplier Foxconn for this product.", "customer"
    )
    assert any("ROLE RISK" in f for f in flags)


def test_internal_language_to_customer():
    flags = check_role_sensitivity(
        "This is internal information about our operations.", "customer"
    )
    assert any("ROLE RISK" in f for f in flags)


def test_misleading_guarantee_to_investor():
    flags = check_role_sensitivity(
        "This investment offers guaranteed return of 20% per annum.", "investor"
    )
    assert any("ROLE RISK" in f for f in flags)


def test_equity_language_to_partner():
    flags = check_role_sensitivity(
        "We need to discuss the equity and profit share split with you.", "partner"
    )
    assert any("ROLE RISK" in f for f in flags)


def test_clean_customer_reply_no_role_risk():
    flags = check_role_sensitivity(
        "Thank you for your order. It will arrive in 5 days.", "customer"
    )
    assert flags == []


def test_neutral_partner_reply_no_role_risk():
    flags = check_role_sensitivity("Your delivery is on track.", "partner")
    assert flags == []


# ── Aggregation / Escalation Checks ─────────────────────────────────────────


def test_pii_flag_aggregates_to_high_with_approval():
    pii_flags = check_pii_leakage("Your SSN is 078-05-1120.")
    level, approval = aggregate_risk(pii_flags)
    assert level == "high"
    assert approval is True


def test_role_risk_aggregates_to_medium_with_approval():
    role_flags = check_role_sensitivity("We source from our supplier Foxconn.", "customer")
    level, approval = aggregate_risk(role_flags)
    assert level == "medium"
    assert approval is True


def test_no_flags_aggregates_to_low_no_approval():
    level, approval = aggregate_risk([])
    assert level == "low"
    assert approval is False
