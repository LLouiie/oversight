import pytest
import requests
from query_decomposition_agent import (
    QueryBranchResult,
    QueryDecompositionAgent,
)

def test_decompose_round1_success_round2_all_success(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="gpt-4o",
        enabled=True,
    )

    # Mock _run_round1 to return a valid dictionary that fits Round1Response
    monkeypatch.setattr(
        agent,
        "_run_round1",
        lambda query_text: {
            "reasoning": "Test reasoning for dynamic thinking.",
            "intent": "test intent",
            "keywords": ["alpha"],
            "constraints": [],
            "facets": [],
            "notes": [],
            "directions": ["direction A", "direction B"],
        },
    )
    
    # Mock _run_round2_parallel
    monkeypatch.setattr(
        agent,
        "_run_round2_parallel",
        lambda query_text, round1_output: [
            QueryBranchResult(branch_id="branch_0", status="success", search_query="query A"),
            QueryBranchResult(branch_id="branch_1", status="success", search_query="query B"),
        ],
    )

    run = agent.decompose("original query")

    assert run.enabled is True
    assert run.round1_status == "success"
    assert len(run.branches) == 2
    assert run.branches[0].search_query == "query A"
    assert run.round1_output["reasoning"] == "Test reasoning for dynamic thinking."

def test_decompose_partial_success(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="gpt-4o",
        enabled=True,
    )

    monkeypatch.setattr(agent, "_run_round1", lambda query_text: {
        "reasoning": "Partial success reasoning",
        "intent": "x",
        "keywords": [],
        "constraints": [],
        "facets": [],
        "notes": [],
        "directions": ["d1", "d2"]
    })
    
    monkeypatch.setattr(
        agent,
        "_run_round2_parallel",
        lambda query_text, round1_output: [
            QueryBranchResult(branch_id="branch_0", status="success", search_query="qa"),
            QueryBranchResult(branch_id="branch_1", status="timeout", error="timeout"),
        ],
    )

    run = agent.decompose("original query")

    assert run.round1_status == "success"
    assert run.partial_success is True
    assert run.has_successful_branch() is True

def test_round2_branch_invalid_json(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="gpt-4o",
        enabled=True,
    )

    # Simulate invalid JSON output from LLM
    monkeypatch.setattr(agent, "_chat_completion", lambda _messages, json_mode: "not-json")

    result = agent._run_round2_branch("branch_1", 1, "systems angle", "q", {"intent": "x"})

    assert result.branch_id == "branch_1"
    assert result.status == "invalid_output"
    assert "ValidationError" in str(result.error) or "JSON" in str(result.error)
