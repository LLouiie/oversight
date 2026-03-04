from datetime import datetime, timedelta
import os
from typing import Any, Dict, List

from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv

from query_decomposition_agent import QueryDecompositionAgent
from linear_rag_search import LinearRAGSearchEngine
from PaperDatabase import PaperDatabase
from ArXivRepository import ArXivRepository
from ResearchListener import research_listener_group
from reranker import BGEReranker

# Load environment variables early so repo/db can connect
load_dotenv()

app = Flask(__name__)
# Allow local Next.js dev server by default; can be customized with CORS_ORIGINS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS(app, resources={r"/api/*": {"origins": cors_origins}})
_search_engine: LinearRAGSearchEngine | None = None
_reranker: BGEReranker | None = None


@app.get("/api/health")
def health() -> tuple[dict, int]:
    return {"status": "ok"}, 200


def _get_reranker() -> BGEReranker | None:
    """
    Singleton getter for the BGE Reranker to avoid reloading the model on every request.
    """
    global _reranker
    if _reranker is not None:
        return _reranker

    # Only load reranker if explicitly enabled via environment variable
    enabled = os.getenv("OVERSIGHT_RERANK_ENABLED", "true").lower() == "true"
    if not enabled:
        return None

    # Using 'BAAI/bge-reranker-base' as default for better local performance (CPU/MPS).
    # 'BAAI/bge-reranker-v2-m3' is much heavier (1GB+).
    model_name = os.getenv("OVERSIGHT_RERANK_MODEL", "BAAI/bge-reranker-base")
    use_fp16 = os.getenv("OVERSIGHT_RERANK_FP16", "true").lower() == "true"
    _reranker = BGEReranker(model_name=model_name, use_fp16=use_fp16)
    return _reranker


def _build_filters(sources_flags: Dict[str, bool]) -> List[str]:
    selected_sources = []

    if sources_flags.get("arxiv", False):
        selected_sources.append("arxiv")

    ai_conferences = ["ICML", "NeurIPS", "ICLR"]
    for conf in ai_conferences:
        if sources_flags.get(conf, False):
            selected_sources.append(conf)

    systems_conferences = ["OSDI", "SOSP", "ASPLOS", "ATC", "NSDI", "MLSys", "EuroSys", "VLDB"]
    for conf in systems_conferences:
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

    repo_root = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.getenv("LINEAR_RAG_DATA_DIR", os.path.join(repo_root, "data"))
    linear_rag_root = os.getenv("LINEAR_RAG_ROOT", os.path.join(repo_root, "LinearRAG"))
    working_dir = os.getenv("LINEAR_RAG_WORKING_DIR", os.path.join(linear_rag_root, "import"))
    dataset_name = os.getenv("LINEAR_RAG_DATASET_NAME", "oversight_data")
    embedding_model_name = os.getenv("LINEAR_RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    spacy_model = os.getenv("LINEAR_RAG_SPACY_MODEL", "en_core_web_sm")
    # Keep default conservative for local stability; users can tune up explicitly.
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


def _dedupe_flat_results(query_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_paper_ids: set[str] = set()
    flattened: list[dict[str, Any]] = []
    for group in query_groups:
        for paper in group.get("results", []) or []:
            paper_id = str(paper.get("paper_id", ""))
            if not paper_id or paper_id in seen_paper_ids:
                continue
            seen_paper_ids.add(paper_id)
            flattened.append(paper)
    return flattened


@app.post("/api/search")
@app.get("/api/search")
def search() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    # Support query params for GET as well
    if request.method == "GET" and not body:
        sources = {
            "arxiv": request.args.get("arxiv", "false").lower() == "true",
        }

        ai_conferences = ["ICML", "NeurIPS", "ICLR"]
        for conf in ai_conferences:
            sources[conf] = request.args.get(conf, "false").lower() == "true"

        systems_conferences = ["OSDI", "SOSP", "ASPLOS", "ATC", "NSDI", "MLSys", "EuroSys", "VLDB"]
        for conf in systems_conferences:
            sources[conf] = request.args.get(conf, "false").lower() == "true"

        body = {
            "text": request.args.get("text", ""),
            "time_window_days": request.args.get("time_window_days"),
            "sources": sources,
        }

    query_text: str = body.get("text", "").strip()
    if not query_text:
        return {"error": "text is required"}, 400

    time_window_days = body.get("time_window_days")
    if time_window_days is None and body.get("start_date"):
        try:
            start_date = datetime.fromisoformat(str(body.get("start_date"))).date()
            delta_days = (datetime.now().date() - start_date).days
            time_window_days = max(1, delta_days)
        except Exception:
            return {"error": "start_date must be in YYYY-MM-DD format"}, 400

    try:
        time_window_days_int = int(time_window_days) if time_window_days is not None else 365 * 5
    except Exception:
        return {"error": "time_window_days must be an integer"}, 400

    limit = body.get("limit")
    try:
        limit_int = int(limit) if limit is not None else 10
        limit_int = max(1, min(100, limit_int))
    except Exception:
        return {"error": "limit must be an integer between 1 and 100"}, 400

    sources_flags: Dict[str, bool] = body.get("sources", {}) or {}
    selected_sources = _build_filters(sources_flags)
    
    # Check if reranking is requested by the client (defaults to false if not specified)
    rerank_requested = body.get("rerank", False)
    rerank_max_input_param = body.get("rerank_max_input")
    
    search_engine = _get_search_engine()
    agent = QueryDecompositionAgent.from_env()
    agent_run = agent.decompose(query_text)
    query_timedelta = timedelta(days=time_window_days_int)

    # If the agent is disabled/unconfigured, preserve legacy single-query search behavior.
    if not agent_run.enabled:
        try:
            papers = search_engine.search_related_papers(
                query_text=query_text,
                query_timedelta=query_timedelta,
                selected_sources=selected_sources,
                limit=limit_int,
            )
        except Exception as exc:
            return {
                "error": f"LinearRAG retrieval failed: {exc}",
                "results": [],
                "query_groups": [],
                "agent": agent_run.agent_meta(include_debug=agent.debug),
            }, 502

        results = [_paper_to_api_dict(p) for p in papers]
        return {
            "results": results,
            "query_groups": [],
            "agent": agent_run.agent_meta(include_debug=agent.debug),
        }, 200

    if agent_run.round1_status == "failed":
        return {
            "error": agent_run.error or "Local agent round 1 failed",
            "results": [],
            "query_groups": [],
            "agent": agent_run.agent_meta(include_debug=agent.debug),
        }, 502

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
                limit=limit_int,
            )
            group_payload["results"] = [_paper_to_api_dict(p) for p in papers]
        except Exception as exc:
            group_payload["status"] = "failed"
            group_payload["error"] = f"Retrieval failed: {exc}"
            group_payload["results"] = []

        query_groups.append(group_payload)

    if not any(group["status"] == "success" for group in query_groups):
        return {
            "error": agent_run.error or "All query branches failed",
            "results": [],
            "query_groups": query_groups,
            "agent": agent_run.agent_meta(include_debug=agent.debug),
        }, 502

    results = _dedupe_flat_results(query_groups)
    
    # Post-process: Re-rank results if requested by the client and the reranker is available
    reranker = _get_reranker()
    if reranker and results and rerank_requested:
        # Re-rank against the original user query for global semantic relevance
        reranked_top_k = int(os.getenv("OVERSIGHT_RERANK_TOP_K", str(limit_int)))
        # Use provided param, else fallback to env/default
        max_rerank_input = int(rerank_max_input_param) if rerank_max_input_param is not None else int(os.getenv("OVERSIGHT_RERANK_MAX_INPUT", "60"))
        
        to_rerank = results[:max_rerank_input]
        others = results[max_rerank_input:]
        
        reranked = reranker.rerank(query=query_text, papers=to_rerank, top_k=reranked_top_k)
        # Combine reranked results with the rest (if top_k is large)
        results = reranked + others[:max(0, limit_int - len(reranked))]

    return {
        "results": results,
        "query_groups": query_groups,
        "agent": agent_run.agent_meta(include_debug=agent.debug),
    }, 200


@app.get("/api/author/papers")
def author_papers() -> tuple[dict, int]:
    author_name = (request.args.get("name") or "").strip()
    if not author_name:
        return {"error": "name is required"}, 400

    limit = request.args.get("limit")
    try:
        limit_int = int(limit) if limit is not None else 100
        limit_int = max(1, min(500, limit_int))
    except Exception:
        return {"error": "limit must be an integer between 1 and 500"}, 400

    with PaperDatabase() as db:
        rows = db.get_papers_by_author(author_name, limit=limit_int)

    results = []
    for paper_id, title, abstract, source, update_date, link in rows:
        results.append({
            "paper_id": paper_id,
            "title": title,
            "abstract": abstract,
            "source": source,
            "link": link,
            "paper_date": update_date.isoformat() if hasattr(update_date, "isoformat") else str(update_date),
        })

    return {"author": author_name, "results": results}, 200


@app.post("/api/sync")
def sync() -> tuple[dict, int]:
    """
    Synchronize ArXiv repository by fetching new papers and embedding them.
    This endpoint initializes an ArXivRepository and calls its sync method.
    """
    try:
        with ArXivRepository(
            embedding_model_name="models/gemini-embedding-001",
            research_llm_model_name="google/gemini-2.5-flash",
        ) as arxiv_repo:
            arxiv_repo.sync()

        return {"status": "success", "message": "ArXiv repository sync completed successfully"}, 200

    except Exception as e:
        app.logger.error(f"Error during ArXiv sync: {str(e)}")
        return {"status": "error", "message": f"Sync failed: {str(e)}"}, 500


@app.post("/api/digest")
def digest() -> tuple[dict, int]:
    """
    Send email digest to research listener group without updating the repository.
    This endpoint initializes an ArXivRepository and calls email_weekly_digest.
    """
    try:
        with ArXivRepository(
            embedding_model_name="models/gemini-embedding-001",
            research_llm_model_name="google/gemini-2.5-flash",
        ) as arxiv_repo:
            arxiv_repo.email_weekly_digest(research_listener_group)

        return {"status": "success", "message": "Email digest sent successfully"}, 200

    except Exception as e:
        app.logger.error(f"Error during digest email: {str(e)}")
        return {"status": "error", "message": f"Digest email failed: {str(e)}"}, 500


if __name__ == "__main__":
    # Pre-load models if enabled to avoid timeouts on first request
    if os.getenv("OVERSIGHT_RERANK_ENABLED", "true").lower() == "true":
        print("[OVERSIGHT] Pre-loading Reranker model...")
        # Reverting to user preferred powerful model
        os.environ.setdefault("OVERSIGHT_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
        _get_reranker()
        
    # Bind to all interfaces for local dev; port can be overridden via FLASK_PORT
    port = int(os.getenv("FLASK_PORT", "5002"))
    # Use project-specific flags so inherited Flask env vars do not accidentally
    # enable auto-reload during long-running LinearRAG indexing.
    debug_enabled = os.getenv("OVERSIGHT_FLASK_DEBUG", "false").lower() == "true"
    use_reloader = os.getenv("OVERSIGHT_FLASK_RELOADER", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_enabled, use_reloader=use_reloader)
