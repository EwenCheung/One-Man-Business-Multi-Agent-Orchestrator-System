from backend.nodes.intake import intake_node


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _FakeSession:
    def query(self, *args, **kwargs):
        return _FakeQuery()

    def add(self, *args, **kwargs):
        return None

    def commit(self):
        return None

    def close(self):
        return None


def test_intake_node_cleans_message_and_sets_defaults(monkeypatch):
    monkeypatch.setattr(
        "backend.nodes.intake.resolve_or_create_sender",
        lambda session, external_sender_id, sender_name: {
            "external_sender_id": external_sender_id,
            "sender_id": "11111111-1111-1111-1111-111111111111",
            "entity_id": "11111111-1111-1111-1111-111111111111",
            "sender_role": "customer",
            "owner_id": "4c116430-f683-4a8a-91f7-546fa8bc5d76",
        },
    )
    monkeypatch.setattr("backend.nodes.intake.SessionLocal", lambda: _FakeSession())

    result = intake_node(
        {
            "raw_message": "  Hello   there   \n what is your return policy?  ",
            "sender_id": "+65 9000 1234",
            "sender_name": "Test Sender",
        }
    )

    assert result["raw_message"] == "Hello there what is your return policy?"
    assert result["intent_label"] == "unknown"
    assert result["urgency_level"] == "normal"
    assert result["sender_role"] == "customer"
    assert result["sender_id"] == "11111111-1111-1111-1111-111111111111"
    assert result["external_sender_id"] == "+65 9000 1234"
