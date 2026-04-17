"""
Merge and rerank helpers for LinearRAG + query-decomposition branches.

When a question bundles multiple distinct subtopics, global reranking against the
full user query can bury one subtopic; optional per-branch rerank + round-robin
interleaving preserves representation from each branch.
"""

from __future__ import annotations

import os
from typing import Any


def dedupe_flat_results(query_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def round_robin_interleave(
    branch_lists: list[list[dict[str, Any]]],
    limit: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    max_len = max((len(b) for b in branch_lists), default=0)
    for i in range(max_len):
        for branch in branch_lists:
            if i >= len(branch):
                continue
            paper = branch[i]
            pid = str(paper.get("paper_id", ""))
            if not pid or pid in seen:
                continue
            seen.add(pid)
            out.append(paper)
            if len(out) >= limit:
                return out
    return out


def merge_linear_rag_agent_results(
    query_groups: list[dict[str, Any]],
    *,
    original_query: str,
    limit: int,
    reranker: Any | None,
    rerank_requested: bool,
    rerank_max_input: int | None,
    expected_subtopics: int | None,
) -> list[dict[str, Any]]:
    """
    Flatten branch results. If expected_subtopics >= 2, combine branches with
    round-robin interleaving (optional per-branch rerank when reranking is on).
    Otherwise preserve legacy behavior: dedupe in branch order, rerank against
    original_query.
    """
    max_in = int(
        rerank_max_input
        if rerank_max_input is not None
        else os.getenv("OVERSIGHT_RERANK_MAX_INPUT", "60")
    )
    try:
        max_in = max(1, min(500, max_in))
    except (TypeError, ValueError):
        max_in = 60

    reranked_top_k = int(os.getenv("OVERSIGHT_RERANK_TOP_K", str(limit)))
    try:
        reranked_top_k = max(1, min(200, reranked_top_k))
    except (TypeError, ValueError):
        reranked_top_k = limit

    try:
        n_sub = int(expected_subtopics) if expected_subtopics is not None else 0
    except (TypeError, ValueError):
        n_sub = 0

    use_multitopic = n_sub >= 2

    if use_multitopic:
        branch_lists: list[list[dict[str, Any]]] = []
        for group in query_groups:
            if group.get("status") != "success":
                branch_lists.append([])
                continue
            papers = list(group.get("results") or [])
            if not papers:
                branch_lists.append([])
                continue
            if rerank_requested and reranker is not None:
                sq = group.get("search_query") or original_query
                trimmed = papers[:max_in]
                rr = reranker.rerank(
                    query=str(sq),
                    papers=trimmed,
                    top_k=min(len(trimmed), reranked_top_k, limit),
                )
                branch_lists.append(rr)
            else:
                branch_lists.append(papers[:limit])
        return round_robin_interleave(branch_lists, limit)

    results = dedupe_flat_results(query_groups)
    if not rerank_requested or not reranker or not results:
        # Match legacy API behavior: do not truncate the merged list when reranking is off.
        return results
    to_rerank = results[:max_in]
    others = results[max_in:]
    reranked = reranker.rerank(
        query=original_query,
        papers=to_rerank,
        top_k=min(reranked_top_k, len(to_rerank)),
    )
    merged = reranked + others[: max(0, limit - len(reranked))]
    return merged
