"""
Recompute recall@k, NDCG@k, per-split summary, and pooled summary from existing
n0/n1/n2_linear_rag_eval.json files — no retrieval, no LLM.

Uses the same matching / NDCG definitions as run_final_query_2602_linear_rag.py.

Example:
  python recompute_final_query_2602_metrics.py --results-dir final_query_2602/linear_rag_results
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_final_query_2602_linear_rag import (
    OUTPUT_NAMES,
    SPLIT_IDS,
    SUMMARY_FILENAME,
    count_ground_truth_hits,
    ndcg_at_k,
)


def _infer_k(payload: dict[str, Any], override: int | None) -> int:
    if override is not None:
        return max(1, min(100, override))
    mk = payload.get("metrics", {}).get("k")
    if isinstance(mk, int) and mk > 0:
        return mk
    qs = payload.get("queries") or []
    if qs and isinstance(qs[0].get("paper_names"), list):
        return len(qs[0]["paper_names"])
    return 10


def _infer_fuzzy(payload: dict[str, Any], override: bool | None) -> bool:
    if override is not None:
        return override
    return bool(payload.get("metrics", {}).get("title_match_fuzzy", False))


def recompute_payload(
    payload: dict[str, Any],
    *,
    k: int,
    fuzzy: bool,
) -> dict[str, Any]:
    queries = payload.get("queries")
    if not isinstance(queries, list):
        raise ValueError("Expected top-level 'queries' list")

    recalls: list[float] = []
    ndcgs: list[float] = []
    any_hit_count = 0
    full_recall_count = 0

    for q in queries:
        if not isinstance(q, dict):
            continue
        gt = list(q.get("ground_truth_titles") or [])
        names = list(q.get("paper_names") or [])
        n_gt = len(gt)
        q["num_ground_truth"] = n_gt

        hits, matched = count_ground_truth_hits(gt, names, fuzzy=fuzzy)
        rec = 0.0 if n_gt == 0 else hits / n_gt
        nd = ndcg_at_k(names, gt, k, fuzzy=fuzzy)

        recalls.append(rec)
        ndcgs.append(nd)
        if hits > 0:
            any_hit_count += 1
        if n_gt > 0 and hits == n_gt:
            full_recall_count += 1

        q["hits_at_k"] = hits
        q["recall_at_k"] = rec
        q["ndcg_at_k"] = nd
        q["matched_ground_truth_titles"] = matched

    nq = len(queries)
    mean_recall = sum(recalls) / nq if nq else 0.0
    median_recall = statistics.median(recalls) if recalls else 0.0
    mean_ndcg = sum(ndcgs) / nq if nq else 0.0
    median_ndcg = statistics.median(ndcgs) if ndcgs else 0.0

    summary_block = {
        "split": (payload.get("summary") or {}).get("split", ""),
        "k": k,
        "num_queries": nq,
        "mean_recall_at_k": mean_recall,
        "median_recall_at_k": median_recall,
        "mean_ndcg_at_k": mean_ndcg,
        "median_ndcg_at_k": median_ndcg,
        "ndcg_note": (
            "Binary relevance vs ground-truth titles; discount log2(rank+1); "
            "IDCG assumes all |GT| relevant docs ranked first."
        ),
    }

    metrics_block = {
        "k": k,
        "num_queries": nq,
        "mean_recall_at_k": mean_recall,
        "median_recall_at_k": median_recall,
        "mean_ndcg_at_k": mean_ndcg,
        "median_ndcg_at_k": median_ndcg,
        "queries_with_any_ground_truth_hit": any_hit_count,
        "queries_with_full_ground_truth_recall": full_recall_count,
        "fraction_queries_with_any_hit": any_hit_count / nq if nq else 0.0,
        "title_match_fuzzy": fuzzy,
    }

    out = dict(payload)
    out["summary"] = summary_block
    out["metrics"] = metrics_block
    rm = out.get("run_metadata")
    if isinstance(rm, dict):
        rm = dict(rm)
        rm["recomputed_metrics"] = True
        out["run_metadata"] = rm
    else:
        out["run_metadata"] = {"recomputed_metrics": True}

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recompute recall/NDCG from saved n*_linear_rag_eval.json (no re-retrieval)."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=REPO_ROOT / "final_query_2602" / "linear_rag_results",
        help="Directory containing n0/n1/n2_linear_rag_eval.json",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Evaluation cutoff k (default: read from each file's metrics.k or first query length)",
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Force fuzzy title matching (overrides JSON metrics.title_match_fuzzy)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Force exact title match only (no fuzzy)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print metrics only; do not write files",
    )
    args = parser.parse_args()

    results_dir: Path = args.results_dir
    if not results_dir.is_dir():
        print(f"Not a directory: {results_dir}", file=sys.stderr)
        sys.exit(1)

    combined_recalls: list[float] = []
    combined_ndcgs: list[float] = []
    split_summaries: dict[str, Any] = {}

    for out_name, split in zip(OUTPUT_NAMES, SPLIT_IDS, strict=True):
        path = results_dir / out_name
        if not path.is_file():
            print(f"Skip missing: {path}", file=sys.stderr)
            continue

        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        k = _infer_k(payload, args.k)
        if args.fuzzy and args.strict:
            print("Use only one of --fuzzy or --strict", file=sys.stderr)
            sys.exit(2)
        fuzzy_override: bool | None = None
        if args.fuzzy:
            fuzzy_override = True
        elif args.strict:
            fuzzy_override = False
        fuzzy = _infer_fuzzy(payload, fuzzy_override)
        updated = recompute_payload(payload, k=k, fuzzy=fuzzy)
        updated["summary"]["split"] = split

        for q in updated["queries"]:
            combined_recalls.append(float(q["recall_at_k"]))
            combined_ndcgs.append(float(q["ndcg_at_k"]))

        split_summaries[split] = {
            "output_file": out_name,
            "num_queries": updated["metrics"]["num_queries"],
            "mean_recall_at_k": updated["metrics"]["mean_recall_at_k"],
            "mean_ndcg_at_k": updated["metrics"]["mean_ndcg_at_k"],
            "median_ndcg_at_k": updated["metrics"]["median_ndcg_at_k"],
        }

        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2, ensure_ascii=True)

        m = updated["metrics"]
        print(
            f"{out_name}: k={k} fuzzy={fuzzy} | "
            f"mean_recall={m['mean_recall_at_k']:.4f} mean_ndcg={m['mean_ndcg_at_k']:.4f}"
        )

    total_q = len(combined_recalls)
    overall = {
        "total_queries": total_q,
        "mean_recall_at_k": sum(combined_recalls) / total_q if total_q else 0.0,
        "mean_ndcg_at_k": sum(combined_ndcgs) / total_q if total_q else 0.0,
        "median_recall_at_k": statistics.median(combined_recalls) if combined_recalls else 0.0,
        "median_ndcg_at_k": statistics.median(combined_ndcgs) if combined_ndcgs else 0.0,
    }

    summary_payload = {
        "summary": {
            "description": "Recomputed from saved eval JSON (no retrieval).",
            "splits": split_summaries,
            "overall": overall,
        },
    }

    if not args.dry_run:
        summary_path = results_dir / SUMMARY_FILENAME
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2, ensure_ascii=True)
        print(f"Wrote {summary_path} | overall mean_ndcg={overall['mean_ndcg_at_k']:.4f}")
    else:
        print(f"[dry-run] overall mean_ndcg={overall['mean_ndcg_at_k']:.4f} (n={total_q})")


if __name__ == "__main__":
    main()
