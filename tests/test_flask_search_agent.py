from datetime import date
import importlib
from types import SimpleNamespace

import pytest

from query_decomposition_agent import QueryBranchResult, QueryDecompositionRun


try:
    flask_app = importlib.import_module("flask_app")
except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific
    pytest.skip(f"Skipping Flask endpoint tests: {exc}", allow_module_level=True)


class FakeSearchEngine:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self._results_by_query = {
            "qa": [
                SimpleNamespace(paper_id="p1", title="P1", abstract="A1", source="ICML", link=None, paper_date=date(2025, 1, 1)),
                SimpleNamespace(paper_id="p2", title="P2", abstract="A2", source="ICLR", link=None, paper_date=date(2025, 1, 2)),
            ],
            "qc": [
                SimpleNamespace(paper_id="p2", title="P2", abstract="A2", source="ICLR", link=None, paper_date=date(2025, 1, 2)),
                SimpleNamespace(paper_id="p3", title="P3", abstract="A3", source="OSDI", link=None, paper_date=date(2025, 1, 3)),
            ],
            "original": [
                SimpleNamespace(paper_id="legacy", title="Legacy", abstract="Legacy abstract", source="arxiv", link=None, paper_date=date(2025, 1, 4)),
            ],
        }

    def search_related_papers(self, query_text, query_timedelta, selected_sources, limit=10):
        self.calls.append(
            {
                "text": query_text,
                "limit": limit,
                "selected_sources": selected_sources,
            }
        )
        return list(self._results_by_query.get(query_text, []))[:limit]


class DisabledAgent:
    debug = False

    def decompose(self, query_text, **kwargs):
        return QueryDecompositionRun(
            enabled=False,
            round1_status="skipped",
            model="",
            base_url=None,
            branches=[],
            error="disabled",
        )


class GroupedAgent:
    debug = True

    def decompose(self, query_text, **kwargs):
        return QueryDecompositionRun(
            enabled=True,
            round1_status="success",
            model="local-model",
            base_url="http://localhost:8000/v1",
            branches=[
                QueryBranchResult(branch_id="branch_0", status="success", search_query="qa"),
                QueryBranchResult(branch_id="branch_1", status="timeout", search_query=None, error="timed out"),
                QueryBranchResult(branch_id="branch_2", status="success", search_query="qc"),
            ],
            partial_success=True,
            round1_output={"intent": "x"},
        )


@pytest.fixture
def client(monkeypatch):
    fake_search_engine = FakeSearchEngine()
    monkeypatch.setattr(flask_app, "_get_search_engine", lambda: fake_search_engine)
    monkeypatch.setattr(flask_app, "_get_reranker", lambda: None)
    return flask_app.app.test_client(), fake_search_engine


def test_search_legacy_fallback_when_agent_disabled(monkeypatch, client):
    http_client, fake_search_engine = client

    monkeypatch.setattr(
        flask_app.QueryDecompositionAgent,
        "from_env",
        classmethod(lambda cls: DisabledAgent()),
    )

    resp = http_client.post(
        "/api/search",
        json={"text": "original", "limit": 5, "sources": {"arxiv": True}},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["agent"]["enabled"] is False
    assert payload["query_groups"] == []
    assert [p["paper_id"] for p in payload["results"]] == ["legacy"]
    assert fake_search_engine.calls[0]["limit"] == 5


def test_search_returns_grouped_results_and_deduped_flat_results(monkeypatch, client):
    http_client, fake_search_engine = client

    monkeypatch.setattr(
        flask_app.QueryDecompositionAgent,
        "from_env",
        classmethod(lambda cls: GroupedAgent()),
    )

    resp = http_client.post(
        "/api/search",
        json={"text": "original", "limit": 2, "sources": {"arxiv": True}},
    )

    assert resp.status_code == 200
    payload = resp.get_json()

    assert payload["agent"]["enabled"] is True
    assert payload["agent"]["partial_success"] is True
    assert len(payload["query_groups"]) == 3
    assert payload["query_groups"][0]["status"] == "success"
    assert payload["query_groups"][1]["status"] == "timeout"
    assert payload["query_groups"][2]["status"] == "success"
    assert [p["paper_id"] for p in payload["results"]] == ["p1", "p2"]

    queried_texts = [call["text"] for call in fake_search_engine.calls]
    assert queried_texts == ["qa", "qc"]
    assert all(call["limit"] == 2 for call in fake_search_engine.calls)


def test_search_requires_text(client):
    http_client, _ = client

    resp = http_client.post("/api/search", json={"text": ""})

    assert resp.status_code == 400
    assert "text is required" in resp.get_json()["error"]
