"""
Batch retrieval over many queries using the same stack as /api/search:
LinearRAGSearchEngine, optional QueryDecompositionAgent, optional BGE rerank.

Input/output JSON shape matches run_query_flat_retrieval.py:
  - Input: query_flat.json (list of { "question": ... }) or multi_output.json (dict values = query text)
  - Output: { "queries": [ { "query_id", "query", "abstract_ids", "paper_names" }, ... ], "run_metadata": { ... } }

Environment: same variables as flask_app (LINEAR_RAG_*, LOCAL_AGENT_*, OVERSIGHT_RERANK_*, etc.).
Does not import Flask (safe to run in environments where only retrieval deps are installed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent.parent
for _p in (REPO_ROOT, EVAL_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dotenv import load_dotenv

load_dotenv(override=True)

from oversight.agent_retrieval_merge import merge_linear_rag_agent_results
from oversight.linear_rag_search import LinearRAGSearchEngine
from oversight.query_decomposition_agent import QueryDecompositionAgent
from oversight.reranker import BGEReranker

_search_engine: LinearRAGSearchEngine | None = None
_reranker: BGEReranker | None = None


def _get_reranker() -> BGEReranker | None:
    global _reranker
    if _reranker is not None:
        return _reranker

    enabled = os.getenv("OVERSIGHT_RERANK_ENABLED", "true").lower() == "true"
    if not enabled:
        return None

    model_name = os.getenv("OVERSIGHT_RERANK_MODEL", "BAAI/bge-reranker-base")
    use_fp16 = os.getenv("OVERSIGHT_RERANK_FP16", "true").lower() == "true"
    _reranker = BGEReranker(model_name=model_name, use_fp16=use_fp16)
    return _reranker


def _build_filters(sources_flags: dict[str, bool]) -> list[str]:
    selected_sources: list[str] = []

    if sources_flags.get("arxiv", False):
        selected_sources.append("arxiv")

    for conf in ["ICML", "NeurIPS", "ICLR"]:
        if sources_flags.get(conf, False):
            selected_sources.append(conf)

    for conf in ["OSDI", "SOSP", "ASPLOS", "ATC", "NSDI", "MLSys", "EuroSys", "VLDB"]:
        if sources_flags.get(conf, False):
            selected_sources.append(conf)

    if selected_sources:
        return selected_sources

    return [
        "arxiv",
        "ICML", "NeurIPS", "ICLR",
        "OSDI", "SOSP", "ASPLOS", "ATC", "NSDI", "MLSys", "EuroSys", "VLDB",
    ]


def _get_search_engine() -> LinearRAGSearchEngine:
    global _search_engine
    if _search_engine is not None:
        return _search_engine

    repo_root = str(REPO_ROOT)
    data_dir = os.getenv("LINEAR_RAG_DATA_DIR", os.path.join(repo_root, "data"))
    linear_rag_root = os.getenv("LINEAR_RAG_ROOT", os.path.join(repo_root, "LinearRAG"))
    working_dir = os.getenv("LINEAR_RAG_WORKING_DIR", os.path.join(linear_rag_root, "import"))
    dataset_name = os.getenv("LINEAR_RAG_DATASET_NAME", "oversight_data")
    embedding_model_name = os.getenv("LINEAR_RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    spacy_model = os.getenv("LINEAR_RAG_SPACY_MODEL", "en_core_web_sm")
    max_workers = int(os.getenv("LINEAR_RAG_MAX_WORKERS", "1"))
    retrieval_pool_size = int(os.getenv("LINEAR_RAG_RETRIEVAL_POOL_SIZE", "120"))
    use_vectorized_retrieval = os.getenv("LINEAR_RAG_USE_VECTORIZED", "false").lower() == "true"

    _search_engine = LinearRAGSearchEngine(
        data_dir=data_dir,
        linear_rag_root=linear_rag_root,
        working_dir=working_dir,
        dataset_name=dataset_name,
        embedding_model_name=embedding_model_name,
        spacy_model=spacy_model,
        max_workers=max_workers,
        retrieval_pool_size=retrieval_pool_size,
        use_vectorized_retrieval=use_vectorized_retrieval,
    )
    return _search_engine


def _paper_to_api_dict(p: Any) -> dict[str, Any]:
    return {
        "paper_id": p.paper_id,
        "title": p.title,
        "abstract": p.abstract,
        "source": p.source,
        "link": p.link,
        "paper_date": p.paper_date.isoformat() if hasattr(p.paper_date, "isoformat") else str(p.paper_date),
    }


def load_queries(path: str) -> list[dict]:
    """Load queries from either query_flat.json format or multi_output.json format."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        queries = []
        for query_text in data.values():
            queries.append({"question": query_text})
        return queries

    return data


def _search_like_api(
    query_text: str,
    *,
    time_window_days: int,
    limit: int,
    selected_sources: list[str],
    rerank_requested: bool,
    rerank_max_input: int | None,
    expected_subtopics: int | None = None,
) -> list[dict[str, Any]]:
    """Match flask_app.search() LinearRAG + agent + rerank behavior."""
    search_engine = _get_search_engine()
    agent = QueryDecompositionAgent.from_env()
    agent_run = agent.decompose(query_text, expected_subtopics=expected_subtopics)
    query_timedelta = timedelta(days=time_window_days)

    if not agent_run.enabled:
        papers = search_engine.search_related_papers(
            query_text=query_text,
            query_timedelta=query_timedelta,
            selected_sources=selected_sources,
            limit=limit,
        )
        return [_paper_to_api_dict(p) for p in papers]

    if agent_run.round1_status == "failed":
        return []

    query_groups: list[dict[str, Any]] = []
    for branch in agent_run.branches:
        group_payload = branch.to_dict()
        group_payload["results"] = []

        if branch.status != "success" or not branch.search_query:
            query_groups.append(group_payload)
            continue

        try:
            papers = search_engine.search_related_papers(
                query_text=branch.search_query,
                query_timedelta=query_timedelta,
                selected_sources=selected_sources,
                limit=limit,
            )
            group_payload["results"] = [_paper_to_api_dict(p) for p in papers]
        except Exception:
            group_payload["status"] = "failed"
            group_payload["error"] = "Retrieval failed"
            group_payload["results"] = []

        query_groups.append(group_payload)

    if not any(group.get("status") == "success" for group in query_groups):
        return []

    reranker = _get_reranker()
    max_rerank_input = (
        int(rerank_max_input)
        if rerank_max_input is not None
        else int(os.getenv("OVERSIGHT_RERANK_MAX_INPUT", "60"))
    )
    results = merge_linear_rag_agent_results(
        query_groups,
        original_query=query_text,
        limit=limit,
        reranker=reranker,
        rerank_requested=rerank_requested,
        rerank_max_input=max_rerank_input,
        expected_subtopics=expected_subtopics,
    )

    return results


def build_results(
    queries: list[dict],
    *,
    limit: int,
    time_window_days: int,
    sources_flags: dict[str, bool],
    rerank: bool,
    rerank_max_input: int | None,
) -> dict[str, Any]:
    selected_sources = _build_filters(sources_flags)
    results: dict[str, Any] = {"queries": []}

    for query_id, query_item in enumerate(queries):
        query_text = query_item.get("question")
        if not query_text:
            continue

        paper_dicts = _search_like_api(
            query_text.strip(),
            time_window_days=time_window_days,
            limit=limit,
            selected_sources=selected_sources,
            rerank_requested=rerank,
            rerank_max_input=rerank_max_input,
        )

        results["queries"].append(
            {
                "query_id": query_id,
                "query": query_text,
                "abstract_ids": [str(p.get("paper_id", "")) for p in paper_dicts],
                "paper_names": [str(p.get("title", "")) for p in paper_dicts],
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch LinearRAG retrieval (same pipeline as /api/search). "
        "Output JSON matches run_query_flat_retrieval.py."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON: query_flat list or multi_output dict",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max papers per query (1–100, same as API)",
    )
    parser.add_argument(
        "--time-window-days",
        type=int,
        default=365 * 50,
        help="Lookback window in days (default: 50 years, similar to legacy flat script)",
    )
    parser.add_argument(
        "--sources-json",
        default="",
        help='Optional path to JSON object of source flags, e.g. {"arxiv": true, "ICML": true}. '
        "If omitted, uses all sources (same as empty body in API).",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Apply BGE rerank when agent decomposition succeeds (same as API rerank=true)",
    )
    parser.add_argument(
        "--rerank-max-input",
        type=int,
        default=None,
        help="Max papers passed to reranker (default: env OVERSIGHT_RERANK_MAX_INPUT or 60)",
    )
    args = parser.parse_args()

    limit = max(1, min(100, args.limit))
    sources_flags: dict[str, bool] = {}
    if args.sources_json.strip():
        with open(args.sources_json, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                sources_flags = {str(k): bool(v) for k, v in raw.items()}

    queries = load_queries(args.input)
    start_time = time.time()
    payload = build_results(
        queries,
        limit=limit,
        time_window_days=args.time_window_days,
        sources_flags=sources_flags,
        rerank=args.rerank,
        rerank_max_input=args.rerank_max_input,
    )
    elapsed_seconds = time.time() - start_time

    linear_embedding = os.getenv("LINEAR_RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    payload["run_metadata"] = {
        "started_at_epoch": int(start_time),
        "elapsed_seconds": elapsed_seconds,
        "query_count": len(payload["queries"]),
        "top_k": limit,
        "retrieval_backend": "linear_rag",
        "embedding_model": linear_embedding,
        "linear_rag_embedding_model": linear_embedding,
        "time_window_days": args.time_window_days,
        "selected_sources": _build_filters(sources_flags),
        "rerank": args.rerank,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)

    print(
        f"Completed {payload['run_metadata']['query_count']} queries in "
        f"{payload['run_metadata']['elapsed_seconds']:.2f}s. "
        f"Output: {out_path}"
    )


if __name__ == "__main__":
    main()
