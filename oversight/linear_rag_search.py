from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import logging
import os
from pathlib import Path
import re
import sys
from threading import Lock
from typing import Any

from oversight.paper import Paper


logger = logging.getLogger(__name__)


class LinearRAGSearchEngine:
    _PAPER_ID_PATTERN = re.compile(r"\[PAPER_ID=([^\]]+)\]")
    # XML 1.0 legal chars (for GraphML serialization):
    # Tab, LF, CR, U+0020..U+D7FF, U+E000..U+FFFD
    _INVALID_XML_CHAR_PATTERN = re.compile(
        r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]"
    )

    def __init__(
        self,
        data_dir: str,
        linear_rag_root: str,
        working_dir: str,
        dataset_name: str,
        embedding_model_name: str,
        spacy_model: str,
        max_workers: int = 8,
        retrieval_pool_size: int = 100,
        use_vectorized_retrieval: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.linear_rag_root = Path(linear_rag_root)
        self.working_dir = working_dir
        self.dataset_name = dataset_name
        self.embedding_model_name = embedding_model_name
        self.spacy_model = spacy_model
        self.max_workers = max_workers
        self.retrieval_pool_size = retrieval_pool_size
        self.use_vectorized_retrieval = use_vectorized_retrieval

        self._lock = Lock()
        self._ready = False
        self._fingerprint: str | None = None
        self._rag: Any = None
        self._papers_by_id: dict[str, Paper] = {}

    def search_related_papers(
        self,
        query_text: str,
        query_timedelta: timedelta | None,
        selected_sources: list[str] | None,
        limit: int,
    ) -> list[Paper]:
        if not query_text.strip():
            return []
        if limit < 1:
            return []

        source_set = set(selected_sources or [])
        with self._lock:
            self._ensure_ready_locked()
            retrieval_top_k = min(
                len(self._papers_by_id),
                max(limit, self.retrieval_pool_size, limit * 8),
            )
            self._rag.config.retrieval_top_k = retrieval_top_k
            retrieval = self._rag.retrieve([{"question": query_text, "answer": ""}])[0]

        cutoff_date: date | None = None
        if query_timedelta is not None:
            cutoff_date = datetime.now().date() - query_timedelta

        deduped_results: list[Paper] = []
        seen_paper_ids: set[str] = set()
        sorted_passages = retrieval.get("sorted_passage", []) or []

        for passage in sorted_passages:
            paper_id = self._extract_paper_id(passage)
            if not paper_id or paper_id in seen_paper_ids:
                continue

            paper = self._papers_by_id.get(paper_id)
            if paper is None:
                continue
            if source_set and paper.source not in source_set:
                continue

            paper_date = self._paper_date(paper)
            if cutoff_date is not None and paper_date < cutoff_date:
                continue

            seen_paper_ids.add(paper_id)
            deduped_results.append(paper)
            if len(deduped_results) >= limit:
                break

        return deduped_results

    def _ensure_ready_locked(self) -> None:
        fingerprint = self._data_fingerprint()
        if self._ready and self._fingerprint == fingerprint:
            return

        if not self.data_dir.exists():
            raise RuntimeError(f"LinearRAG data directory does not exist: {self.data_dir}")

        papers = self._load_papers()
        if not papers:
            raise RuntimeError(
                f"No usable papers found in {self.data_dir}. "
                "Expected JSON arrays with title/abstract/date fields."
            )

        rag_model = self._build_rag_model()
        passages = [self._paper_to_passage(i, p) for i, p in enumerate(papers)]
        logger.info("LinearRAG indexing %d passages from %s", len(passages), self.data_dir)
        rag_model.index(passages)

        self._papers_by_id = {paper.paper_id: paper for paper in papers}
        self._rag = rag_model
        self._fingerprint = fingerprint
        self._ready = True
        logger.info("LinearRAG index is ready with %d papers", len(self._papers_by_id))

    def _build_rag_model(self) -> Any:
        if not self.linear_rag_root.exists():
            raise RuntimeError(
                f"LinearRAG project path does not exist: {self.linear_rag_root}"
            )

        if str(self.linear_rag_root) not in sys.path:
            sys.path.insert(0, str(self.linear_rag_root))

        try:
            from sentence_transformers import SentenceTransformer
            from src.config import LinearRAGConfig
            from src.LinearRAG import LinearRAG
        except Exception as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                f"LinearRAG retrieval failed: LinearRAG dependencies are missing. "
                "Install at least: sentence-transformers, spacy, python-igraph, torch. "
                f"(Original error: {exc})"
            ) from exc

        try:
            embedding_model = SentenceTransformer(
                self.embedding_model_name,
                device=os.getenv("LINEAR_RAG_DEVICE", "cpu"),
            )
        except Exception as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                f"Failed to load embedding model '{self.embedding_model_name}'. "
                "Set LINEAR_RAG_EMBEDDING_MODEL to a valid local path or model name."
            ) from exc

        config = LinearRAGConfig(
            dataset_name=self.dataset_name,
            embedding_model=embedding_model,
            llm_model=None,
            spacy_model=self.spacy_model,
            working_dir=self.working_dir,
            max_workers=self.max_workers,
            retrieval_top_k=max(10, self.retrieval_pool_size),
            use_vectorized_retrieval=self.use_vectorized_retrieval,
        )

        try:
            return LinearRAG(global_config=config)
        except Exception as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                f"Failed to initialize LinearRAG with spaCy model '{self.spacy_model}'. "
                "If needed, install it with: python -m spacy download en_core_web_sm"
            ) from exc

    def _load_papers(self) -> list[Paper]:
        papers_by_id: dict[str, Paper] = {}
        json_files = sorted(self.data_dir.rglob("*.json"))
        for json_file in json_files:
            with open(json_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            if not isinstance(payload, list):
                continue

            for idx, raw_paper in enumerate(payload):
                paper = self._parse_paper(raw_paper, json_file, idx)
                if paper is None:
                    continue

                existing = papers_by_id.get(paper.paper_id)
                if existing is None or paper.paper_date > existing.paper_date:
                    papers_by_id[paper.paper_id] = paper

        # Deterministic order improves reproducibility of graph generation.
        return sorted(
            papers_by_id.values(),
            key=lambda p: (p.paper_date, p.source or "", p.paper_id),
        )

    def _parse_paper(
        self,
        raw_paper: dict[str, Any],
        source_file: Path,
        index_in_file: int,
    ) -> Paper | None:
        if not isinstance(raw_paper, dict):
            return None

        title = self._clean_text(raw_paper.get("title"))
        abstract = self._clean_text(raw_paper.get("abstract"))
        if not title or not abstract:
            return None

        paper_date = self._parse_date(raw_paper.get("date"))
        if paper_date is None:
            return None

        source = (
            self._clean_text(raw_paper.get("conference_name"))
            or self._clean_text(raw_paper.get("source"))
            or source_file.stem.split("_")[0].upper()
        )
        paper_id = self._clean_text(raw_paper.get("paper_id")) or f"{source_file.stem}-{index_in_file}"
        link = self._clean_text(raw_paper.get("link")) or self._clean_text(raw_paper.get("conference_link"))

        try:
            return Paper.from_scraped_json(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "date": paper_date.strftime(Paper.date_format()),
                    "link": link,
                    "conference_name": source,
                }
            )
        except Exception:
            return None

    def _paper_to_passage(self, index: int, paper: Paper) -> str:
        title = paper.title.replace("\n", " ").strip()
        abstract = paper.abstract.replace("\n", " ").strip()
        paper_date = paper.paper_date.isoformat()
        source = paper.source or ""
        return (
            f"{index}: [PAPER_ID={paper.paper_id}] [SOURCE={source}] [DATE={paper_date}] "
            f"Title: {title}. Abstract: {abstract}"
        )

    def _extract_paper_id(self, passage_text: str) -> str | None:
        match = self._PAPER_ID_PATTERN.search(passage_text or "")
        return match.group(1) if match else None

    def _data_fingerprint(self) -> str:
        parts: list[str] = []
        for path in sorted(self.data_dir.rglob("*.json")):
            stat = path.stat()
            parts.append(f"{path.relative_to(self.data_dir)}:{stat.st_size}:{stat.st_mtime_ns}")
        return "|".join(parts)

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        cleaned = str(value).replace("\x00", "")
        cleaned = LinearRAGSearchEngine._INVALID_XML_CHAR_PATTERN.sub("", cleaned)
        return cleaned.strip()

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        text = text[:10]
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _paper_date(paper: Paper) -> date:
        if isinstance(paper.paper_date, datetime):
            return paper.paper_date.date()
        return paper.paper_date
