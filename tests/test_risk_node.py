"""
Risk Node Tests — verify correct risk classification.

## TODO
- [ ] Test low-risk reply → risk_level="low", requires_approval=False
- [ ] Test reply with price commitment → risk_level="medium"
- [ ] Test reply with legal/contract language → risk_level="high", requires_approval=True
- [ ] Test reply leaking internal margins to customer → confidentiality flag
- [ ] Test reply leaking cost prices to supplier → confidentiality flag
- [ ] Test escalation triggers: legal action, safety, contract breach
"""


def test_risk_node_returns_structure():
    """Risk node should return risk_level, risk_flags, requires_approval."""
    from backend.nodes.risk import risk_node

    state = {"reply_text": "Hello, thanks for reaching out!", "sender_role": "customer"}
    result = risk_node(state)

    assert "risk_level" in result
    assert "risk_flags" in result
    assert "requires_approval" in result
    assert result["risk_level"] in ("low", "medium", "high")
