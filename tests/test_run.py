import asyncio
import os
import sys
from pprint import pprint

# Ensure we're running from project root for imports
sys.path.append(os.getcwd())

# Dummy settings to avoid load issues if keys aren't set in CI/env
from backend.config import settings
if not settings.OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not found in settings. Orchestrator LLM call will likely fail.")

from backend.agents.orchestrator_agent import orchestrator_agent

def run_test(test_name: str, state: dict):
    print(f"\n{'='*50}")
    print(f"TEST: {test_name}")
    print(f"{'='*50}")
    
    try:
        result = orchestrator_agent(state)
        
        # Format output cleanly
        print("\n[ACTIVE TASKS ASSIGNED]")
        if result.get("active_tasks"):
            for t in result["active_tasks"]:
                print(f" -> [{t['assignee']}] (Priority: {t['priority']})")
                print(f"    Description: {t['description']}")
                print(f"    Context Needed: {t['context_needed']}")
                print(f"    Depends On: {t['depends_on']}")
        else:
            print(" -> [NONE]")
            
        print("\n[ROUTE TO REPLY]:", result.get("route_to_reply"))
        print("\n[PLAN STEPS]:")
        for log in result.get("plan_steps", []):
            print(log)
            
        if result.get("orchestrator_warnings"):
            print("\n[WARNINGS]:", result.get("orchestrator_warnings"))
            
    except Exception as e:
        print(f"\n[ERROR] {e}")


def main():
    # Test 1: Needs information
    state_1 = {
        "raw_message": "Hi, I need to know our return policy for damaged laptops. Can you also tell me if we have 50x ThinkPads in stock?",
        "sender_name": "Alice",
        "sender_role": "Customer",
        "intent_label": "Inquiry",
        "urgency_level": "Medium",
        "rules_context": "Strictly no discounts > 10%.",
        "long_term_memory": "Client always wants expedited shipping.",
        "short_term_memory": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "replan_count": 0
    }
    
    run_test("1. Initial Request (Needs Info)", state_1)
    
    # Test 2: Has all information, should reply
    state_2 = {
        "raw_message": "Can I get a 15% discount on 100 laptops?",
        "sender_name": "Bob",
        "sender_role": "Partner",
        "intent_label": "Negotiation",
        "urgency_level": "High",
        "rules_context": "Strictly no discounts > 10%.",
        "long_term_memory": "Valued partner, usually orders bulk.",
        "short_term_memory": [],
        "completed_tasks": [
            {
                "task_id": "1", 
                "assignee": "policy", 
                "result": "Discounts above 10% are strictly forbidden. You must decline politely.",
                "status": "completed"
            },
            {
                "task_id": "2",
                "assignee": "retriever",
                "result": "We have 150 laptops in stock.",
                "status": "completed"
            }
        ],
        "failed_tasks": [],
        "replan_count": 1
    }
    
    run_test("2. Follow-up (Has Info, Ready to Reply)", state_2)


if __name__ == "__main__":
    main()
