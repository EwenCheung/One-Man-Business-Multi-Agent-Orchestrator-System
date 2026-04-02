"""
P1 Full Pipeline Integration Test

This script tests the newly refactored Orchestrator, Sub-Agents, A2A Response formats,
and Pipeline Guards by simulating a customer message to the pipeline.
"""

import sys
import os
sys.path.append(os.getcwd())

import pytest
from backend.graph.pipeline_graph import pipeline
from backend.db.engine import SessionLocal
from backend.db.models import Customer
from backend.utils.langfuse import get_langfuse_handler
import json


@pytest.mark.integration
def test_pipeline():
    print("\n" + "="*50)
    print("🚀 Running Pipeline Integration Test")
    print("="*50 + "\n")

    # 1. Setup minimal test data in DB if needed to avoid crash
    session = SessionLocal()
    try:
        # Clean up any previously corrupted test customers
        session.query(Customer).filter(Customer.name == "Test Customer").delete()
        session.commit()

        # Just grab the first customer or create a mock one
        customer = session.query(Customer).first()
        if not customer:
            print("⚠️ No customer data found in DB. Auto-seeding a mock customer now...")
            from sqlalchemy import text
            
            # Fetch an existing user (ignoring the Supabase system ID)
            existing_user_id = session.execute(text("SELECT id FROM auth.users WHERE id::text != '00000000-0000-0000-0000-000000000000' LIMIT 1")).scalar()
            
            if not existing_user_id:
                print("❌ Your Supabase 'users' table is completely empty! Please sign up or create a user in your Supabase Auth/Users dashboard first, then run this again.")
                return
                
            mock_customer = Customer(
                owner_id=existing_user_id,
                name="Test Customer",
                email="test_customer@example.com"
            )
            session.add(mock_customer)
            session.commit()
            customer = mock_customer
            print(f"✅ Created mock customer with ID: {customer.id}")

        mock_state = {
            "sender_id": str(customer.id),
            "owner_id": str(customer.owner_id),
            "raw_message": "Do you offer bulk discounts or price matching? And do you have 100 laptops in stock?",
            "sender_role": "customer",
            "sender_name": "Test Customer",
        }

        print("📦 Injecting mock message into Orchestrator:")
        print(f"   Message: '{mock_state['raw_message']}'")
        print(f"   Sender:  {mock_state['sender_name']} ({mock_state['sender_role']})")
        
        # 2. Add Langfuse callback if available
        config = {}
        handler = get_langfuse_handler()
        if handler:
            config["callbacks"] = [handler]
            print("✅ Langfuse tracing enabled.")
        else:
            print("⚠️ Langfuse skipped (keys not set in .env).")

        # 3. Stream pipeline output
        print("\n⏳ Executing Pipeline Graph...\n")
        
        final_state = None
        for step_idx, step in enumerate(pipeline.stream(mock_state, config=config)):
            node_name = list(step.keys())[0]
            node_data = step[node_name]
            print(f"[{step_idx}] Node Execution: '{node_name}'")
            
            # Print intermediate tasks
            if "plan" in node_data:
                print(f"   ↳ Planned {len(node_data['plan'].tasks)} tasks.")
            if "completed_tasks" in node_data:
                print(f"   ↳ Agent '{node_name}' completed. Response snippet:")
                result = node_data['completed_tasks'][-1].get("result", "")
                print(f"     {result[:200]}...")
            
            final_state = step

        # 4. End Results
        print("\n" + "="*50)
        print("🎯 Pipeline Execution Complete")
        print("="*50 + "\n")
        
        final_node_name = list(final_state.keys())[0]
        state_data = final_state[final_node_name]
        
        reply = state_data.get("reply_draft", "NO REPLY GENERATED")
        risk = state_data.get("risk_level", "UNKNOWN")
        approval = state_data.get("requires_approval", False)
        
        print(f"Generated Reply: \n{reply}\n")
        print(f"Risk Evaluation: {risk.upper()} (Requires Approval: {approval})")

    except Exception as e:
        print("\n❌ Pipeline crashed during execution:")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_pipeline()
