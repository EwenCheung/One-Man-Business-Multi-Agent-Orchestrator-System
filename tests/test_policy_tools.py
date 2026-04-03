from backend.tools.policy_tools import infer_policy_categories, merge_policy_candidates


def test_infer_policy_categories_for_discount_and_approval():
    categories = infer_policy_categories(
        "Can I offer a custom discount and do I need owner approval?",
        "customer",
    )
    assert "pricing" in categories
    assert "owner_benefit" in categories


def test_infer_policy_categories_for_supplier_role():
    categories = infer_policy_categories("What are our invoice payment terms?", "supplier")
    assert "supplier" in categories


def test_merge_policy_candidates_deduplicates_by_chunk_id():
    merged = merge_policy_candidates(
        [
            {
                "chunk_id": "a",
                "chunk_text": "semantic",
                "source_file": "pricing_policy.pdf",
                "page_number": 1,
                "subheading": "Pricing",
                "category": "pricing",
                "hard_constraint": True,
                "similarity_score": 0.72,
                "retrieval_mode": "semantic",
            }
        ],
        [
            {
                "chunk_id": "a",
                "chunk_text": "lexical",
                "source_file": "pricing_policy.pdf",
                "page_number": 1,
                "subheading": "Pricing",
                "category": "pricing",
                "hard_constraint": True,
                "similarity_score": 5.0,
                "retrieval_mode": "lexical",
            },
            {
                "chunk_id": "b",
                "chunk_text": "other",
                "source_file": "owner_benefit_rules.pdf",
                "page_number": 1,
                "subheading": "Approval",
                "category": "owner_benefit",
                "hard_constraint": True,
                "similarity_score": 2.0,
                "retrieval_mode": "lexical",
            },
        ],
    )

    assert [candidate["chunk_id"] for candidate in merged] == ["a", "b"]
    assert merged[0]["chunk_text"] == "lexical"
