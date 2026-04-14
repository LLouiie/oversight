from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Dict, List

import streamlit as st

from query_decomposition_agent import QueryDecompositionAgent

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


AI_CONFERENCES = ["ICML", "NeurIPS", "ICLR"]
SYSTEMS_CONFERENCES = ["OSDI", "SOSP", "ASPLOS", "ATC", "NSDI", "MLSys", "EuroSys", "VLDB"]
ALL_SOURCES = ["arxiv"] + AI_CONFERENCES + SYSTEMS_CONFERENCES


def _build_filters(repo: Any, sources_flags: Dict[str, bool]) -> List[str]:
    selected_sources = [source for source in ALL_SOURCES if sources_flags.get(source, False)]
    if selected_sources:
        return [repo.build_filter_string(selected_sources)]
    return [repo.build_filter_string(ALL_SOURCES)]


def _paper_to_dict(p: Any) -> dict[str, Any]:
    return {
        "paper_id": p.paper_id,
        "title": p.title,
        "abstract": p.abstract,
        "source": p.source,
        "link": p.link,
        "paper_date": p.paper_date.isoformat() if hasattr(p.paper_date, "isoformat") else str(p.paper_date),
    }


def _dedupe_flat_results(query_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for group in query_groups:
        for row in group.get("results", []) or []:
            paper_id = str(row.get("paper_id", ""))
            if not paper_id or paper_id in seen:
                continue
            seen.add(paper_id)
            out.append(row)
    return out


def run_search(
    query_text: str,
    time_window_days: int,
    limit: int,
    sources_flags: Dict[str, bool],
) -> dict[str, Any]:
    try:
        from PaperRepository import PaperRepository
    except Exception as exc:
        return {
            "results": [],
            "query_groups": [],
            "agent": {},
            "error": (
                "Failed to import PaperRepository. "
                "Please verify your Python environment has database dependencies installed "
                f"(original error: {exc})"
            ),
        }

    agent = QueryDecompositionAgent.from_env()
    agent_run = agent.decompose(query_text)
    query_timedelta = timedelta(days=time_window_days)

    if not agent_run.enabled:
        with PaperRepository(embedding_model_name="models/gemini-embedding-001") as repo:
            filters = _build_filters(repo, sources_flags)
            papers = repo.get_newest_related_papers(
                query_text,
                query_timedelta,
                filters,
                limit=limit,
            )
        return {
            "results": [_paper_to_dict(p) for p in papers],
            "query_groups": [],
            "agent": agent_run.agent_meta(include_debug=agent.debug),
            "error": None,
        }

    if agent_run.round1_status == "failed":
        return {
            "results": [],
            "query_groups": [],
            "agent": agent_run.agent_meta(include_debug=agent.debug),
            "error": agent_run.error or "Round 1 failed",
        }

    query_groups: list[dict[str, Any]] = []
    with PaperRepository(embedding_model_name="models/gemini-embedding-001") as repo:
        filters = _build_filters(repo, sources_flags)
        for branch in agent_run.branches:
            group = branch.to_dict()
            group["results"] = []
            if branch.status != "success" or not branch.search_query:
                query_groups.append(group)
                continue

            try:
                papers = repo.get_newest_related_papers(
                    branch.search_query,
                    query_timedelta,
                    filters,
                    limit=limit,
                )
                group["results"] = [_paper_to_dict(p) for p in papers]
            except Exception as exc:
                group["status"] = "failed"
                group["error"] = f"Retrieval failed: {exc}"
                group["results"] = []

            query_groups.append(group)

    error = None
    if not any(group["status"] == "success" for group in query_groups):
        error = agent_run.error or "All query branches failed"

    return {
        "results": _dedupe_flat_results(query_groups),
        "query_groups": query_groups,
        "agent": agent_run.agent_meta(include_debug=agent.debug),
        "error": error,
    }


def _branch_label(branch_id: str) -> str:
    match = re.fullmatch(r"branch_(\d+)", branch_id)
    if match:
        return str(int(match.group(1)) + 1)
    mapping = {"branch_a": "A", "branch_b": "B", "branch_c": "C"}
    return mapping.get(branch_id, branch_id)


def _render_paper_card(row: dict[str, Any], key_prefix: str) -> None:
    st.markdown(f"**{row.get('title', '(untitled)')}**")
    st.caption(
        f"{row.get('source', '')} | {row.get('paper_date', '')} | {row.get('paper_id', '')}"
    )
    st.write(row.get("abstract", ""))
    link = row.get("link")
    if link:
        st.markdown(f"[Open paper]({link})")
    st.divider()


def main() -> None:
    st.set_page_config(page_title="Oversight Agent Search", layout="wide")
    st.title("Oversight Agent Search (Streamlit)")
    st.caption("Two-round agent decomposition -> one retrieval per model-chosen direction")

    with st.sidebar:
        st.header("Search Controls")
        time_days = st.slider("Lookback window (days)", min_value=7, max_value=3650, value=365 * 5, step=1)
        limit = st.slider("Max results per branch", min_value=1, max_value=100, value=10, step=1)
        selected_sources = st.multiselect("Sources", options=ALL_SOURCES, default=ALL_SOURCES)
        show_flat = st.checkbox("Show deduped flat results", value=True)

    sources_flags = {source: source in selected_sources for source in ALL_SOURCES}
    query_text = st.text_area(
        "Query",
        height=180,
        placeholder="Paste your abstract or research query...",
    )

    if st.button("Run Agent Search", type="primary"):
        if not query_text.strip():
            st.error("Query is required.")
            return

        with st.spinner("Running round-1, round-2 (parallel), and retrieval..."):
            payload = run_search(
                query_text=query_text.strip(),
                time_window_days=time_days,
                limit=limit,
                sources_flags=sources_flags,
            )

        st.subheader("Agent Meta")
        st.json(payload.get("agent", {}))

        if payload.get("error"):
            st.error(payload["error"])

        groups = payload.get("query_groups", []) or []
        if groups:
            st.subheader("Query Groups")
            for group in groups:
                title = f"Branch {_branch_label(str(group.get('branch_id', '')))} | {group.get('status', '')}"
                with st.expander(title, expanded=True):
                    st.write("Search query:")
                    st.code(group.get("search_query") or "(none)", language="text")
                    if group.get("error"):
                        st.warning(group["error"])

                    branch_rows = group.get("results", []) or []
                    if not branch_rows:
                        st.info("No results for this branch.")
                    else:
                        for idx, row in enumerate(branch_rows):
                            _render_paper_card(row, f"{group.get('branch_id', 'branch')}-{idx}")
        else:
            st.info("No query groups returned (agent disabled or fallback mode).")

        if show_flat:
            st.subheader("Flat Deduped Results")
            flat_rows = payload.get("results", []) or []
            if not flat_rows:
                st.info("No flat results.")
            else:
                for idx, row in enumerate(flat_rows):
                    _render_paper_card(row, f"flat-{idx}")


if __name__ == "__main__":
    main()
