"""
Skeleton tests — verify imports and structure work for Supervisor graph.
"""

import importlib


def test_agents_import():
    """All agent modules should be importable."""
    agents = [
        "backend.agents.orchestrator_agent",
        "backend.agents.retrieval_agent",
        "backend.agents.research_agent",
        "backend.agents.policy_agent",
        "backend.agents.reply_agent",
        "backend.agents.memory_agent",
    ]
    for module_name in agents:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Failed to import {module_name}"


def test_nodes_import():
    """All node modules should be importable."""
    nodes = [
        "backend.nodes.intake",
        "backend.nodes.risk",
    ]
    for module_name in nodes:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Failed to import {module_name}"


def test_graph_state_import():
    """Graph state should be importable."""
    from backend.graph.state import PipelineState
    from backend.graph.pipeline_graph import pipeline

    assert PipelineState is not None
    assert pipeline is not None


def test_models_import():
    """Models should be importable."""
    from backend.models import IncomingMessage, PipelineResult

    assert IncomingMessage is not None
    assert PipelineResult is not None


def test_app_import():
    """FastAPI app should be importable."""
    from backend.main import app

    assert app is not None
