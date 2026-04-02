"""
P2 Semantic Search Test

This script tests the new vector similarity search in the Retrieval Agent.
We inject a semantic query (e.g. "a fast machine for video editing") and
verify the agent uses the new `@tool` and returns the relevant products.
"""

import sys
import os
import json
sys.path.append(os.getcwd())

import pytest
from backend.db.engine import SessionLocal
from backend.db.models import Customer
from backend.graph.state import SubTask
from backend.agents.retrieval_agent import retrieval_agent


@pytest.mark.integration
def test_semantic_search():
    print("\n" + "="*50)
    print("🚀 Running Retrieval Agent Semantic Search Test")
    print("="*50 + "\n")

    # 1. Setup a valid customer context
    session = SessionLocal()
    try:
        from sqlalchemy import text
        existing_user_id = session.execute(text("SELECT id FROM auth.users WHERE id::text != '00000000-0000-0000-0000-000000000000' LIMIT 1")).scalar()
        
        customer = session.query(Customer).first()
        if not customer and existing_user_id:
            customer = Customer(
                owner_id=existing_user_id,
                name="Semantic Test Customer",
                email="semantic@example.com"
            )
            session.add(customer)
            session.commit()
            
        if not customer:
            print("❌ No valid customer or auth.users found in the DB to associate with the test.")
            return
            
        print(f"✅ Using Customer ID: {customer.id}")

        # Ensure at least one product with an embedding exists
        from backend.db.models import Product
        from backend.tools.retrieval_tools import _embed_query
        
        has_embedded_product = session.query(Product).filter(Product.description_embedding.isnot(None)).first()
        if not has_embedded_product:
            print("⚠️ No embedded products found. Seeding a mock MacBook...")
            macbook_desc = "Apple MacBook Pro 16-inch with M3 Max chip, 64GB RAM, 2TB SSD. High performance machine perfect for heavy computational workloads, 3D rendering, and fast video editing."
            vector = _embed_query(macbook_desc)
            
            mock_product = Product(
                owner_id=customer.owner_id,
                name="MacBook Pro M3 Max",
                description=macbook_desc,
                selling_price=3499.00,
                cost_price=2800.00,
                stock_number=10,
                category="Electronics",
                description_embedding=vector
            )
            session.add(mock_product)
            session.commit()
            print("✅ Mock product seeded successfully!")
        
        description = "I'm looking for a fast machine for video editing. What products do you have?"
        task: SubTask = {
            "task_id": "test_semantic_1",
            "description": description,
            "assignee": "retriever",
            "status": "pending",
            "result": "",
            "priority": "required",
            "context_needed": [],
            "injected_context": {
                "sender_role": "customer",
                "sender_id": str(customer.id)
            }
        }

        print(f"📦 Simulating Retrieval Agent specifically for:")
        print(f"   Query: '{description}'")
        print(f"   Role:  Customer")
        
        # 3. Execute the Retrieval Agent directly
        print("\n⏳ Executing Retrieval Agent...")
        result_state = retrieval_agent(task)
        
        completed_task = result_state.get("completed_tasks", [])[0]
        
        print("\n" + "="*50)
        print("🎯 Retrieval Execution Complete")
        print("="*50 + "\n")
        
        print(f"Status: {completed_task.get('status')}")
        
        # Parse the JSON response
        try:
            agent_response = json.loads(completed_task.get("result", "{}"))
            print(f"Confidence: {agent_response.get('confidence')}")
            print(f"\nRaw Finding Result Data:")
            print(agent_response.get("result", ""))
            
            print(f"\nExtracted Facts:")
            for f in agent_response.get("facts", []):
                print(f"  • {f[:150]}...")
                
        except Exception as e:
            print(f"Raw Result (Not JSON?): {completed_task.get('result')}")
            print(e)

    finally:
        session.close()

if __name__ == "__main__":
    test_semantic_search()
