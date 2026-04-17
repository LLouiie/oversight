import requests

from query_decomposition_agent import (
    QueryBranchResult,
    QueryDecompositionAgent,
)


def test_decompose_round1_success_round2_all_success(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="local-model",
        enabled=True,
        debug=True,
    )

    monkeypatch.setattr(agent, "_prompts_configured", lambda: True)
    monkeypatch.setattr(
        agent,
        "_run_round1",
        lambda query_text, expected_subtopics=None: {
            "intent": "test intent",
            "keywords": ["alpha"],
            "constraints": [],
            "facets": [],
            "notes": [],
            "directions": ["a", "b", "c"],
            "raw": {"intent": "test intent"},
        },
    )
    monkeypatch.setattr(
        agent,
        "_run_round2_parallel",
        lambda query_text, round1_output: [
            QueryBranchResult(branch_id="branch_0", status="success", search_query="qa"),
            QueryBranchResult(branch_id="branch_1", status="success", search_query="qb"),
            QueryBranchResult(branch_id="branch_2", status="success", search_query="qc"),
        ],
    )

    run = agent.decompose("original query")

    assert run.enabled is True
    assert run.round1_status == "success"
    assert run.partial_success is False
    assert [b.search_query for b in run.branches] == ["qa", "qb", "qc"]
    assert run.agent_meta(include_debug=True)["debug"]["round1_output"]["intent"] == "test intent"


def test_decompose_partial_success(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="local-model",
        enabled=True,
    )

    monkeypatch.setattr(agent, "_prompts_configured", lambda: True)
    monkeypatch.setattr(
        agent,
        "_run_round1",
        lambda query_text, expected_subtopics=None: {
            "intent": "x",
            "keywords": [],
            "constraints": [],
            "facets": [],
            "notes": [],
            "raw": {},
        },
    )
    monkeypatch.setattr(
        agent,
        "_run_round2_parallel",
        lambda query_text, round1_output: [
            QueryBranchResult(branch_id="branch_0", status="success", search_query="qa"),
            QueryBranchResult(branch_id="branch_1", status="timeout", error="timeout"),
            QueryBranchResult(branch_id="branch_2", status="success", search_query="qc"),
        ],
    )

    run = agent.decompose("original query")

    assert run.round1_status == "success"
    assert run.partial_success is True
    assert run.has_successful_branch() is True


def test_round2_branch_timeout(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="local-model",
        enabled=True,
    )

    def raise_timeout(_messages):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(agent, "_chat_completion", raise_timeout)

    result = agent._run_round2_branch("branch_0", 0, "method angle", "q", {"intent": "x"})

    assert result.branch_id == "branch_0"
    assert result.status == "timeout"
    assert result.search_query is None


def test_round2_branch_invalid_json(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="local-model",
        enabled=True,
    )

    monkeypatch.setattr(agent, "_chat_completion", lambda _messages: "not-json")

    result = agent._run_round2_branch("branch_1", 1, "systems angle", "q", {"intent": "x"})

    assert result.branch_id == "branch_1"
    assert result.status == "invalid_output"
    assert "JSON" in (result.error or "")


def test_decompose_disabled_when_prompts_are_placeholders(monkeypatch):
    agent = QueryDecompositionAgent(
        base_url="http://localhost:8000/v1",
        model="local-model",
        enabled=True,
    )

    monkeypatch.setattr(agent, "_prompts_configured", lambda: False)

    run = agent.decompose("query")

    assert run.enabled is False
    assert run.round1_status == "skipped"
    assert "placeholders" in (run.error or "")
