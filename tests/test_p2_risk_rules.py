"""
test_p2_risk_rules.py — Unit tests for the new P2 risk rule checkers.

Tests:
  - check_pii_leakage():      credit cards, SSNs, API keys, passwords, IBAN
  - check_role_sensitivity(): customer, investor, partner role-specific risks
  - aggregate_risk():         PII → HIGH, role risk → MEDIUM
"""

from backend.nodes.risk_rules import (
    check_pii_leakage,
    check_role_sensitivity,
    aggregate_risk,
)

PASS = "\033[32m✅ PASS\033[0m"
FAIL = "\033[31m❌ FAIL\033[0m"


def assert_contains(flags, keyword, test_name):
    if any(keyword.lower() in f.lower() for f in flags):
        print(f"{PASS} {test_name}")
    else:
        print(f"{FAIL} {test_name}\n     Expected '{keyword}' in flags: {flags}")


def assert_empty(flags, test_name):
    if not flags:
        print(f"{PASS} {test_name}")
    else:
        print(f"{FAIL} {test_name}\n     Expected NO flags, got: {flags}")


def assert_level(level, expected, approval, expected_approval, test_name):
    if level == expected and approval == expected_approval:
        print(f"{PASS} {test_name}")
    else:
        print(f"{FAIL} {test_name}\n     Expected ({expected}, approval={expected_approval}), got ({level}, approval={approval})")


print()
print("=" * 60)
print("  P2 Risk Rules — Unit Test Suite")
print("=" * 60)
print()

# ── PII Checks ─────────────────────────────────────────────────
print("── PII Leakage Checks ──────────────────────────")

flags = check_pii_leakage("Your card 4111111111111111 has been charged.")
assert_contains(flags, "Credit card", "Credit card number detected")

flags = check_pii_leakage("Your SSN is 123-45-6789 per our records.")
assert_contains(flags, "SSN", "US SSN detected")

flags = check_pii_leakage("Auth with sk-abcdefghijklmnopqrstuvwxyz1234 to call the API.")
assert_contains(flags, "API/Secret", "API key (sk- prefix) detected")

flags = check_pii_leakage("password:mysecret123 has been reset.")
assert_contains(flags, "Password", "Password literal detected")

flags = check_pii_leakage("Your IBAN is GB29NWBK60161331926819 for bank transfers.")
assert_contains(flags, "IBAN", "IBAN/bank account detected")

flags = check_pii_leakage("Thank you for your order! We will ship within 3 days.")
assert_empty(flags, "Clean reply — no PII flags")

# ── Role Sensitivity Checks ────────────────────────────────────
print()
print("── Role-Based Sensitivity Checks ──────────────")

flags = check_role_sensitivity("We source from our supplier Foxconn for this product.", "customer")
assert_contains(flags, "ROLE RISK", "Supplier name exposed to customer")

flags = check_role_sensitivity("This is internal information about our operations.", "customer")
assert_contains(flags, "ROLE RISK", "Internal/confidential language to customer")

flags = check_role_sensitivity(
    "This investment offers guaranteed return of 20% per annum.", "investor"
)
assert_contains(flags, "ROLE RISK", "Misleading guarantee to investor")

flags = check_role_sensitivity(
    "We need to discuss the equity and profit share split with you.", "partner"
)
assert_contains(flags, "ROLE RISK", "Equity/profit-share language to partner")

flags = check_role_sensitivity("Thank you for your order. It will arrive in 5 days.", "customer")
assert_empty(flags, "Clean customer reply — no role risk")

flags = check_role_sensitivity("Your delivery is on track.", "partner")
assert_empty(flags, "Neutral partner reply — no role risk")

# ── Aggregation Checks ─────────────────────────────────────────
print()
print("── Aggregation / Escalation Checks ────────────")

pii_flags = check_pii_leakage("Your SSN is 078-05-1120.")
level, approval = aggregate_risk(pii_flags)
assert_level(level, "high", approval, True, "PII flag → HIGH + approval required")

role_flags = check_role_sensitivity("We source from our supplier Foxconn.", "customer")
level, approval = aggregate_risk(role_flags)
assert_level(level, "medium", approval, True, "Role risk → MEDIUM + approval required")

level, approval = aggregate_risk([])
assert_level(level, "low", approval, False, "No flags → LOW + no approval needed")

print()
print("=" * 60)
print("  All tests complete.")
print("=" * 60)
