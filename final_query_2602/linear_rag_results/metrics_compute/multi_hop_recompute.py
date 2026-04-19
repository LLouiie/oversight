#!/usr/bin/env python3
"""
Recompute n0/n1/n2 eval metrics after replacing ground truth titles with
`top5_overlap_papers` aligned by original GT title.

Notes:
- Empty ground truth after replacement is skipped from metric aggregation.
- Writes updated per-split eval JSONs and a merged summary JSON (with metrics_by_k).
- Paths are configurable via CLI; no hardcoded absolute paths.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = SCRIPT_DIR.parent
DEFAULT_OUT_DIR = SCRIPT_DIR
DEFAULT_OVERLAP_DIR = SCRIPT_DIR.parent / "groundtruth"

# Allow importing from repo root: scripts.eval.run_final_query_2602_linear_rag
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.eval.run_final_query_2602_linear_rag import count_ground_truth_hits, ndcg_at_k


def metrics_by_k_for_queries(
    queries: list[dict[str, Any]],
    ks: list[int],
    fuzzy: bool,
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for k in ks:
        recalls: list[float] = []
        ndcgs: list[float] = []
        for q in queries:
            gt = list(q.get("ground_truth_titles") or [])
            names = list(q.get("paper_names") or [])
            if not gt:
                continue
            hits, _ = count_ground_truth_hits(gt, names[:k], fuzzy=fuzzy)
            recalls.append(hits / len(gt))
            ndcgs.append(ndcg_at_k(names, gt, k, fuzzy=fuzzy))
        n = len(recalls)
        out[str(k)] = {
            "mean_recall_at_k": (sum(recalls) / n) if n else 0.0,
            "mean_ndcg_at_k": (sum(ndcgs) / n) if n else 0.0,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Replace GT with top5_overlap_papers (aligned by original GT title), "
            "skip empty GT queries, and recompute metrics including metrics_by_k."
        )
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory containing n0/n1/n2_linear_rag_eval.json",
    )
    parser.add_argument(
        "--overlap-dir",
        type=Path,
        default=DEFAULT_OVERLAP_DIR,
        help="Directory containing top5_overlap_for_n0/n1/n2.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for updated per-split eval JSONs and summary JSON",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["n0", "n1", "n2"],
        help="Split IDs to process (default: n0 n1 n2)",
    )
    args = parser.parse_args()

    results_dir = args.results_dir
    overlap_dir = args.overlap_dir
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    report_ks = [1, 3, 5, 10]
    split_summaries: dict[str, Any] = {}
    combined_queries_ran: list[dict[str, Any]] = []
    overall_k = 10
    overall_fuzzy = False

    for split in args.splits:
        eval_path = results_dir / f"{split}_linear_rag_eval.json"
        jsonl_path = overlap_dir / f"top5_overlap_for_{split}.jsonl"
        if not eval_path.exists() or not jsonl_path.exists():
            print(f"[skip split missing] {split}")
            continue

        with eval_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        # Mapping: original GT title -> top5_overlap_papers
        title_to_top5: dict[str, list[str]] = {}
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                paper_names = obj.get("paper_names") or []
                if not paper_names:
                    continue
                title = str(paper_names[0]).strip()
                top5 = [str(x).strip() for x in (obj.get("top5_overlap_papers") or []) if str(x).strip()]
                title_to_top5[title] = top5

        queries = payload.get("queries", [])
        fuzzy = bool((payload.get("metrics") or {}).get("title_match_fuzzy", False))
        overall_fuzzy = fuzzy
        k = int((payload.get("metrics") or {}).get("k", 10))
        overall_k = k

        ran_count = 0
        skipped_count = 0
        recalls: list[float] = []
        ndcgs: list[float] = []
        any_hit_count = 0
        full_recall_count = 0

        for q in queries:
            old_gt = q.get("ground_truth_titles") or []
            old_title = str(old_gt[0]).strip() if old_gt else ""
            new_gt = title_to_top5.get(old_title, [])

            q["ground_truth_titles"] = new_gt
            q["num_ground_truth"] = len(new_gt)

            if not new_gt:
                skipped_count += 1
                q["skipped_empty_ground_truth"] = True
                q["hits_at_k"] = 0
                q["recall_at_k"] = None
                q["ndcg_at_k"] = None
                q["matched_ground_truth_titles"] = []
                continue

            names = list(q.get("paper_names") or [])
            hits, matched = count_ground_truth_hits(new_gt, names[:k], fuzzy=fuzzy)
            rec = hits / len(new_gt)
            nd = ndcg_at_k(names, new_gt, k, fuzzy=fuzzy)

            q["skipped_empty_ground_truth"] = False
            q["hits_at_k"] = hits
            q["recall_at_k"] = rec
            q["ndcg_at_k"] = nd
            q["matched_ground_truth_titles"] = matched

            ran_count += 1
            recalls.append(rec)
            ndcgs.append(nd)
            if hits > 0:
                any_hit_count += 1
            if hits == len(new_gt):
                full_recall_count += 1

        mean_recall = (sum(recalls) / ran_count) if ran_count else 0.0
        median_recall = statistics.median(recalls) if recalls else 0.0
        mean_ndcg = (sum(ndcgs) / ran_count) if ran_count else 0.0
        median_ndcg = statistics.median(ndcgs) if ndcgs else 0.0

        ran_queries = [q for q in queries if not q.get("skipped_empty_ground_truth")]
        ks = [kk for kk in report_ks if kk <= k] or [k]
        mbk = metrics_by_k_for_queries(ran_queries, ks, fuzzy)

        payload["summary"] = {
            "split": split,
            "k": k,
            "num_queries": ran_count,
            "skipped_queries_empty_ground_truth": skipped_count,
            "total_queries_before_skip": len(queries),
            "mean_recall_at_k": mean_recall,
            "median_recall_at_k": median_recall,
            "mean_ndcg_at_k": mean_ndcg,
            "median_ndcg_at_k": median_ndcg,
            "ndcg_note": "Binary relevance; empty ground truth queries are skipped.",
        }
        payload["metrics"] = {
            "k": k,
            "num_queries": ran_count,
            "skipped_queries_empty_ground_truth": skipped_count,
            "total_queries_before_skip": len(queries),
            "mean_recall_at_k": mean_recall,
            "median_recall_at_k": median_recall,
            "mean_ndcg_at_k": mean_ndcg,
            "median_ndcg_at_k": median_ndcg,
            "queries_with_any_ground_truth_hit": any_hit_count,
            "queries_with_full_ground_truth_recall": full_recall_count,
            "fraction_queries_with_any_hit": (any_hit_count / ran_count) if ran_count else 0.0,
            "title_match_fuzzy": fuzzy,
        }

        rm = payload.get("run_metadata") or {}
        rm["ground_truth_replaced_from"] = str(jsonl_path)
        rm["recomputed_with_skip_empty_ground_truth"] = True
        payload["run_metadata"] = rm

        out_eval = out_dir / f"{split}_linear_rag_eval.json"
        with out_eval.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        split_summaries[split] = {
            "output_file": out_eval.name,
            "num_queries": ran_count,
            "skipped_queries_empty_ground_truth": skipped_count,
            "total_queries_before_skip": len(queries),
            "mean_recall_at_k": mean_recall,
            "mean_ndcg_at_k": mean_ndcg,
            "median_ndcg_at_k": median_ndcg,
            "metrics_by_k": mbk,
        }

        combined_queries_ran.extend(ran_queries)
        print(f"{split}: ran={ran_count}, skipped={skipped_count}, total={len(queries)}")

    overall_mbk = metrics_by_k_for_queries(
        combined_queries_ran,
        [kk for kk in report_ks if kk <= overall_k] or [overall_k],
        overall_fuzzy,
    )

    overall_recalls = [float(q["recall_at_k"]) for q in combined_queries_ran]
    overall_ndcgs = [float(q["ndcg_at_k"]) for q in combined_queries_ran]
    total_ran = len(combined_queries_ran)
    total_before = sum(v.get("total_queries_before_skip", 0) for v in split_summaries.values())
    total_skipped = sum(v.get("skipped_queries_empty_ground_truth", 0) for v in split_summaries.values())

    overall = {
        "total_queries": total_ran,
        "k": overall_k,
        "mean_recall_at_k": (sum(overall_recalls) / total_ran) if total_ran else 0.0,
        "mean_ndcg_at_k": (sum(overall_ndcgs) / total_ran) if total_ran else 0.0,
        "median_recall_at_k": statistics.median(overall_recalls) if overall_recalls else 0.0,
        "median_ndcg_at_k": statistics.median(overall_ndcgs) if overall_ndcgs else 0.0,
        "metrics_by_k": overall_mbk,
        "skipped_queries_empty_ground_truth": total_skipped,
        "total_queries_before_skip": total_before,
    }

    summary_payload = {
        "summary": {
            "description": "Recomputed after replacing GT with top5_overlap_papers (aligned by original GT title); empty GT skipped.",
            "k": overall_k,
            "splits": split_summaries,
            "overall": overall,
        },
        "run_metadata": {
            "title_match_fuzzy": overall_fuzzy,
            "ground_truth_source_dir": str(overlap_dir),
            "output_dir": str(out_dir),
        },
    }

    out_summary = out_dir / "linear_rag_eval_summary.json"
    with out_summary.open("w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote: {out_summary}")
    print(f"overall ran={total_ran}, skipped={total_skipped}, total_before_skip={total_before}")


if __name__ == "__main__":
    main()
