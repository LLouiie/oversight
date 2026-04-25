"""
Batch-evaluate benchmark/ inputs (n0 / n1 / n2) through the same LinearRAG + agent
stack as /api/search, write three result JSONs, and report recall@k.

Input format (per file): JSON object whose
  - key   = repr of a list of ground-truth paper titles, e.g. "['Title A', 'Title B']"
  - value = synthetic query text

For each query, ``len(ground_truth_titles)`` is passed to the query-decomposition agent as
``expected_subtopics`` so Round 1 aims for that many directions; merge/rerank uses a
multi-branch-friendly path when that count is >= 2.

Set ``LINEAR_RAG_AGENT_EXPECTED_SUBTOPICS`` (e.g. ``5``) to override that count—useful when
re-ranking against multihop overlap labels with five target papers while the input key still
lists three seed titles.

Outputs (default): <output-dir>/n0_linear_rag_eval.json, n1_..., n2_..., plus
`linear_rag_eval_summary.json` with pooled recall/NDCG across splits.

Each per-split file has a top-level `summary`, `queries[]` (with `ndcg_at_k` per row),
`metrics`, and `run_metadata`. NDCG is binary by title match; discount 1/log2(rank+1); IDCG
assumes all ground-truth titles occupy the top ranks.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent.parent
for _p in (REPO_ROOT, EVAL_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dotenv import load_dotenv

load_dotenv(override=False)

from run_query_flat_retrieval_linear_rag import (
    _build_filters,
    _search_like_api,
)

INPUT_FILES = (
    "sampled_multi_paper_entities_n0_output.json",
    "sampled_multi_paper_entities_n1_output.json",
    "sampled_multi_paper_entities_n2_output.json",
)

OUTPUT_NAMES = (
    "n0_linear_rag_eval.json",
    "n1_linear_rag_eval.json",
    "n2_linear_rag_eval.json",
)

SPLIT_IDS = ("n0", "n1", "n2")

SUMMARY_FILENAME = "linear_rag_eval_summary.json"
REPORT_KS = (1, 3, 5, 10)


def _norm_title(t: str) -> str:
    return " ".join(t.split()).strip().casefold()


def parse_ground_truth_key(key: str) -> list[str]:
    """Parse dataset key into a list of title strings."""
    try:
        obj = ast.literal_eval(key)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"Cannot parse ground-truth key as Python literal: {key[:120]}...") from exc
    if isinstance(obj, (list, tuple)):
        return [str(x).strip() for x in obj if str(x).strip()]
    s = str(obj).strip()
    return [s] if s else []


def resolve_agent_expected_subtopics(num_seed_papers: int) -> int:
    """
    Branch count for QueryDecompositionAgent. Default: one branch per seed paper in the key.

    Override with env ``LINEAR_RAG_AGENT_EXPECTED_SUBTOPICS`` (integer 1–16), e.g. 5 when
    evaluating retrieval against five multihop overlap targets while the key still has three titles.
    """
    raw = os.getenv("LINEAR_RAG_AGENT_EXPECTED_SUBTOPICS", "").strip()
    if raw.isdigit():
        return max(1, min(16, int(raw)))
    return max(1, int(num_seed_papers))


def count_ground_truth_hits(
    gt_titles: list[str],
    retrieved_titles: list[str],
    *,
    fuzzy: bool,
) -> tuple[int, list[str]]:
    """
    Return (hit_count, matched_gt_titles). Matching is by normalized full-string equality;
    optional fuzzy: long-title substring containment if no exact match.
    """
    rnorm_full = [_norm_title(p) for p in retrieved_titles]
    rset = set(rnorm_full)
    matched: list[str] = []

    for t in gt_titles:
        nt = _norm_title(t)
        if not nt:
            continue
        if nt in rset:
            matched.append(t)
            continue
        if not fuzzy:
            continue
        ok = False
        for rn in rnorm_full:
            if len(nt) < 12 or len(rn) < 12:
                continue
            if nt in rn or rn in nt:
                ok = True
                break
        if ok:
            matched.append(t)

    return len(matched), matched


def _title_matches_any_gt(retrieved: str, gt_titles: list[str], *, fuzzy: bool) -> bool:
    hits, _ = count_ground_truth_hits(gt_titles, [retrieved], fuzzy=fuzzy)
    return hits > 0


def dcg_at_k(
    retrieved_titles: list[str],
    gt_titles: list[str],
    k: int,
    *,
    fuzzy: bool,
) -> float:
    """Binary relevance: rel_i=1 if retrieved title matches any GT at rank i (1-based DCG discount)."""
    dcg = 0.0
    for i, rt in enumerate(retrieved_titles[:k]):
        rank = i + 1
        rel = 1.0 if _title_matches_any_gt(rt, gt_titles, fuzzy=fuzzy) else 0.0
        dcg += rel / math.log2(rank + 1)
    return dcg


def idcg_at_k(num_ground_truth: int, k: int) -> float:
    """Ideal DCG: all relevant items at the top ranks (binary gain 1 each)."""
    if num_ground_truth <= 0:
        return 0.0
    g = min(num_ground_truth, k)
    return sum(1.0 / math.log2(i + 1) for i in range(1, g + 1))


def ndcg_at_k(
    retrieved_titles: list[str],
    gt_titles: list[str],
    k: int,
    *,
    fuzzy: bool,
) -> float:
    idcg = idcg_at_k(len(gt_titles), k)
    if idcg <= 0.0:
        return 0.0
    return dcg_at_k(retrieved_titles, gt_titles, k, fuzzy=fuzzy) / idcg


def aggregate_metrics_by_k(
    queries: list[dict[str, Any]],
    *,
    ks: list[int],
    fuzzy_title_match: bool,
) -> dict[str, dict[str, float]]:
    by_k: dict[str, dict[str, float]] = {}
    if not queries:
        for k in ks:
            by_k[str(k)] = {"mean_recall_at_k": 0.0, "mean_ndcg_at_k": 0.0}
        return by_k

    for k in ks:
        recalls: list[float] = []
        ndcgs: list[float] = []
        for q in queries:
            gt_titles = list(q.get("ground_truth_titles") or [])
            names = list(q.get("paper_names") or [])
            n_gt = len(gt_titles)
            hits, _ = count_ground_truth_hits(gt_titles, names[:k], fuzzy=fuzzy_title_match)
            rec = 0.0 if n_gt == 0 else hits / n_gt
            nd = ndcg_at_k(names, gt_titles, k, fuzzy=fuzzy_title_match)
            recalls.append(rec)
            ndcgs.append(nd)
        nq = len(queries)
        by_k[str(k)] = {
            "mean_recall_at_k": sum(recalls) / nq if nq else 0.0,
            "mean_ndcg_at_k": sum(ndcgs) / nq if nq else 0.0,
        }
    return by_k


def run_one_input_file(
    input_path: Path,
    *,
    split: str,
    limit: int,
    time_window_days: int,
    sources_flags: dict[str, bool],
    rerank: bool,
    rerank_max_input: int | None,
    fuzzy_title_match: bool,
) -> dict[str, Any]:
    t_start = time.time()
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {input_path}")

    selected_sources = _build_filters(sources_flags)
    queries_out: list[dict[str, Any]] = []
    recalls: list[float] = []
    ndcgs: list[float] = []
    any_hit_count = 0
    full_recall_count = 0
    agent_subtopics_resolved = 3

    for query_id, (raw_key, query_text) in enumerate(data.items()):
        if not query_text or not str(query_text).strip():
            continue
        gt_titles = parse_ground_truth_key(raw_key)
        q = str(query_text).strip()
        agent_subtopics_resolved = resolve_agent_expected_subtopics(len(gt_titles))

        paper_dicts = _search_like_api(
            q,
            time_window_days=time_window_days,
            limit=limit,
            selected_sources=selected_sources,
            rerank_requested=rerank,
            rerank_max_input=rerank_max_input,
            expected_subtopics=agent_subtopics_resolved,
        )
        names = [str(p.get("title", "")) for p in paper_dicts]
        ids = [str(p.get("paper_id", "")) for p in paper_dicts]

        n_gt = len(gt_titles)
        hits, matched = count_ground_truth_hits(gt_titles, names, fuzzy=fuzzy_title_match)
        if n_gt == 0:
            rec = 0.0
        else:
            rec = hits / n_gt
        recalls.append(rec)
        if hits > 0:
            any_hit_count += 1
        if n_gt > 0 and hits == n_gt:
            full_recall_count += 1

        nd = ndcg_at_k(names, gt_titles, limit, fuzzy=fuzzy_title_match)
        ndcgs.append(nd)

        queries_out.append(
            {
                "query_id": query_id,
                "query": q,
                "ground_truth_titles": gt_titles,
                "abstract_ids": ids,
                "paper_names": names,
                "num_ground_truth": n_gt,
                "hits_at_k": hits,
                "recall_at_k": rec,
                "ndcg_at_k": nd,
                "matched_ground_truth_titles": matched,
            }
        )

    nq = len(queries_out)
    mean_recall = sum(recalls) / nq if nq else 0.0
    median_recall = statistics.median(recalls) if recalls else 0.0
    mean_ndcg = sum(ndcgs) / nq if nq else 0.0
    median_ndcg = statistics.median(ndcgs) if ndcgs else 0.0

    linear_embedding = os.getenv("LINEAR_RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    elapsed = time.time() - t_start

    return {
        "summary": {
            "split": split,
            "k": limit,
            "num_queries": nq,
            "mean_recall_at_k": mean_recall,
            "median_recall_at_k": median_recall,
            "mean_ndcg_at_k": mean_ndcg,
            "median_ndcg_at_k": median_ndcg,
            "ndcg_note": (
                "Binary relevance vs ground-truth titles; discount log2(rank+1); "
                "IDCG assumes all |GT| relevant docs ranked first."
            ),
        },
        "queries": queries_out,
        "metrics": {
            "k": limit,
            "num_queries": nq,
            "mean_recall_at_k": mean_recall,
            "median_recall_at_k": median_recall,
            "mean_ndcg_at_k": mean_ndcg,
            "median_ndcg_at_k": median_ndcg,
            "queries_with_any_ground_truth_hit": any_hit_count,
            "queries_with_full_ground_truth_recall": full_recall_count,
            "fraction_queries_with_any_hit": any_hit_count / nq if nq else 0.0,
            "title_match_fuzzy": fuzzy_title_match,
        },
        "run_metadata": {
            "input_file": str(input_path),
            "started_at_epoch": int(t_start),
            "elapsed_seconds": elapsed,
            "retrieval_backend": "linear_rag",
            "embedding_model": linear_embedding,
            "linear_rag_embedding_model": linear_embedding,
            "top_k": limit,
            "time_window_days": time_window_days,
            "selected_sources": selected_sources,
            "rerank": rerank,
            "agent_expected_subtopics": (
                "LINEAR_RAG_AGENT_EXPECTED_SUBTOPICS if set, else len(ground_truth_titles); "
                "passed to QueryDecompositionAgent.decompose"
            ),
            "linear_rag_agent_expected_subtopics_resolved": agent_subtopics_resolved,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LinearRAG (+agent) on benchmark/ n0/n1/n2 files and compute recall@k."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "benchmark",
        help="Directory containing sampled_multi_paper_entities_n{0,1,2}_output.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write three eval JSONs (default: <data-dir>/linear_rag_results)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Top-k retrieval / recall@k (1–100)")
    parser.add_argument(
        "--time-window-days",
        type=int,
        default=365 * 50,
        help="Lookback window (days)",
    )
    parser.add_argument(
        "--sources-json",
        default="",
        help='Optional JSON file of source flags, e.g. {"arxiv": true, ...}',
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="BGE rerank after successful agent merge (same as API)",
    )
    parser.add_argument("--rerank-max-input", type=int, default=None)
    parser.add_argument(
        "--fuzzy-titles",
        action="store_true",
        help="If set, use long-substring fallback when exact title match fails",
    )
    args = parser.parse_args()

    limit = max(1, min(100, args.limit))
    data_dir: Path = args.data_dir
    out_dir: Path = args.output_dir or (data_dir / "linear_rag_results")
    out_dir.mkdir(parents=True, exist_ok=True)

    sources_flags: dict[str, bool] = {}
    if args.sources_json.strip():
        with open(args.sources_json, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                sources_flags = {str(k): bool(v) for k, v in raw.items()}

    report_ks = sorted({k for k in REPORT_KS if k <= limit} or {limit})
    combined_queries: list[dict[str, Any]] = []
    split_summaries: dict[str, Any] = {}

    for in_name, out_name, split in zip(INPUT_FILES, OUTPUT_NAMES, SPLIT_IDS, strict=True):
        in_path = data_dir / in_name
        if not in_path.is_file():
            print(f"Skip missing input: {in_path}", file=sys.stderr)
            continue

        payload = run_one_input_file(
            in_path,
            split=split,
            limit=limit,
            time_window_days=args.time_window_days,
            sources_flags=sources_flags,
            rerank=args.rerank,
            rerank_max_input=args.rerank_max_input,
            fuzzy_title_match=args.fuzzy_titles,
        )

        combined_queries.extend(payload["queries"])
        split_metrics_by_k = aggregate_metrics_by_k(
            payload["queries"],
            ks=report_ks,
            fuzzy_title_match=args.fuzzy_titles,
        )

        split_summaries[split] = {
            "input_file": in_name,
            "output_file": out_name,
            "num_queries": payload["metrics"]["num_queries"],
            "mean_recall_at_k": payload["metrics"]["mean_recall_at_k"],
            "mean_ndcg_at_k": payload["metrics"]["mean_ndcg_at_k"],
            "median_ndcg_at_k": payload["metrics"]["median_ndcg_at_k"],
            "metrics_by_k": split_metrics_by_k,
        }

        out_path = out_dir / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=True)

        m = payload["metrics"]
        per_k_text = " ".join(
            (
                f"R@{k}={split_metrics_by_k[str(k)]['mean_recall_at_k']:.4f} "
                f"NDCG@{k}={split_metrics_by_k[str(k)]['mean_ndcg_at_k']:.4f}"
            )
            for k in report_ks
        )
        print(
            f"Wrote {out_path} | queries={m['num_queries']} "
            f"mean_recall@{limit}={m['mean_recall_at_k']:.4f} "
            f"mean_ndcg@{limit}={m['mean_ndcg_at_k']:.4f} "
            f"any_hit={m['queries_with_any_ground_truth_hit']}/{m['num_queries']} "
            f"| {per_k_text}"
        )

    overall_by_k = aggregate_metrics_by_k(
        combined_queries,
        ks=report_ks,
        fuzzy_title_match=args.fuzzy_titles,
    )
    total_q = len(combined_queries)
    overall = {
        "total_queries": total_q,
        "k": limit,
        "mean_recall_at_k": overall_by_k[str(limit)]["mean_recall_at_k"],
        "mean_ndcg_at_k": overall_by_k[str(limit)]["mean_ndcg_at_k"],
        "median_recall_at_k": statistics.median([float(q["recall_at_k"]) for q in combined_queries]) if combined_queries else 0.0,
        "median_ndcg_at_k": statistics.median([float(q["ndcg_at_k"]) for q in combined_queries]) if combined_queries else 0.0,
        "metrics_by_k": overall_by_k,
    }

    summary_payload = {
        "summary": {
            "description": "Pooled metrics over all queries in n0, n1, n2 (each query weighted equally).",
            "k": limit,
            "splits": split_summaries,
            "overall": overall,
        },
        "run_metadata": {
            "title_match_fuzzy": args.fuzzy_titles,
            "rerank": args.rerank,
            "time_window_days": args.time_window_days,
        },
    }

    summary_path = out_dir / SUMMARY_FILENAME
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=True)
    overall_per_k_text = " ".join(
        (
            f"R@{k}={overall_by_k[str(k)]['mean_recall_at_k']:.4f} "
            f"NDCG@{k}={overall_by_k[str(k)]['mean_ndcg_at_k']:.4f}"
        )
        for k in report_ks
    )
    print(
        f"Wrote {summary_path} | overall mean_ndcg@{limit}={overall['mean_ndcg_at_k']:.4f} "
        f"| {overall_per_k_text}"
    )


if __name__ == "__main__":
    main()
