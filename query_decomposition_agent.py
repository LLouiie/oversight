from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests
from pydantic import BaseModel, Field, ValidationError, model_validator

# --- Pydantic Models for Structured Output ---

from pydantic import BaseModel, Field, ValidationError, model_validator, BeforeValidator
from typing import Annotated

def _ensure_list(v: Any) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [str(i) for i in v]
    return []

StrList = Annotated[list[str], BeforeValidator(_ensure_list)]

class Round1Response(BaseModel):
    """Schema for the first stage of query decomposition in CS/AI research."""
    reasoning: str = Field(description="Internal technical analysis of the query's unique structure and challenges.")
    intent: str = Field(description="A short summary of the user's research goal.")
    keywords: StrList = Field(default_factory=list)
    constraints: StrList = Field(default_factory=list)
    facets: StrList = Field(default_factory=list)
    notes: StrList = Field(default_factory=list)
    directions: StrList = Field(
        default_factory=list,
        description="List of distinct retrieval angles (at least 2 and at most 5 directions)."
    )

    @model_validator(mode='after')
    def ensure_directions(self) -> 'Round1Response':
        """Fallback logic to ensure at least 2 directions exist and enforce max limit."""
        if len(self.directions) < 2:
            # If model failed to give 2, try to append intent or keywords as fallback directions
            fallback = self.intent if self.intent else "General technical implementation"
            if not self.directions:
                self.directions = [f"{fallback} (Primary)"]
            
            while len(self.directions) < 2:
                self.directions.append(f"{fallback} (Alternative Angle {len(self.directions)})")
        
        # Truncate if it exceeds 5
        if len(self.directions) > 5:
            self.directions = self.directions[:5]
            
        return self

class Round2Response(BaseModel):
    """Schema for the second stage: generating a specific high-density search query."""
    search_query: str = Field(min_length=5, description="An expert-level, keyword-dense search string.")

# --- Utility Helpers ---

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts" / "query_decomposition"
ROUND1_PROMPT_PATH = PROMPTS_DIR / "round1.md"
ROUND2_PROMPT_PATH = PROMPTS_DIR / "round2.md"

def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None: return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def _string_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

# --- Result Containers ---

@dataclass
class QueryBranchResult:
    branch_id: str
    status: str
    search_query: str | None = None
    error: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "status": self.status,
            "search_query": self.search_query,
            "error": self.error,
            "results": self.results,
        }

@dataclass
class QueryDecompositionRun:
    enabled: bool
    round1_status: str
    model: str
    base_url: str | None
    branches: list[QueryBranchResult]
    partial_success: bool = False
    error: str | None = None
    round1_output: dict[str, Any] | None = None

    def has_successful_branch(self) -> bool:
        return any(b.status == "success" and bool((b.search_query or "").strip()) for b in self.branches)

    def agent_meta(self, include_debug: bool) -> dict[str, Any]:
        meta = {"enabled": self.enabled, "round1_status": self.round1_status, 
                "partial_success": self.partial_success, "model": self.model}
        if self.base_url: meta["base_url"] = self.base_url
        if self.error: meta["error"] = self.error
        if include_debug and self.round1_output: meta["debug"] = {"round1_output": self.round1_output}
        return meta

# --- Main Agent Class ---

class QueryDecompositionAgent:
    def __init__(self, **kwargs):
        """Initialize agent with environment or constructor settings."""
        self.mode = _string_env("QUERY_DECOMPOSITION_AGENT_MODE", "local").lower()
        prefix = "REMOTE_AGENT_LLM_" if self.mode == "remote" else "LOCAL_AGENT_LLM_"
        
        self.base_url = (kwargs.get("base_url") or _string_env(f"{prefix}BASE_URL")).strip()
        self.model = (kwargs.get("model") or _string_env(f"{prefix}MODEL")).strip()
        self.api_key = kwargs.get("api_key") or _string_env(f"{prefix}API_KEY")
        
        timeout_raw = kwargs.get("timeout_seconds") or _string_env(f"{prefix}TIMEOUT_SECONDS", "20")
        self.timeout_seconds = float(timeout_raw)
        
        self.enabled = _bool_env("LOCAL_AGENT_ENABLED", True) if kwargs.get("enabled") is None else kwargs["enabled"]
        # Enforce range [2, 5] for max directions as per user request
        self.max_directions = max(2, min(5, _int_env("QUERY_DECOMPOSITION_MAX_DIRECTIONS", 5)))
        
        self.round1_prompt_template = self._load_prompt_file(ROUND1_PROMPT_PATH)
        self.round2_prompt_template = self._load_prompt_file(ROUND2_PROMPT_PATH)

    def _load_prompt_file(self, path: Path) -> str:
        """Reads prompt content from file."""
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def _chat_completion(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        """Executes chat completion with optional JSON mode enforcement."""
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content if isinstance(content, str) else json.dumps(content)

    def decompose(self, query_text: str) -> QueryDecompositionRun:
        """Entry point for splitting a query into multiple retrieval branches."""
        if not self.enabled or not self.base_url or not self.model:
            return QueryDecompositionRun(enabled=False, round1_status="skipped", model=self.model, 
                                       base_url=self.base_url, branches=[], error="Configuration missing")

        try:
            # Step 1: Analyze and split
            round1_data = self._run_round1(query_text)
            
            # Step 2: Generate search queries in parallel
            branches = self._run_round2_parallel(query_text, round1_data)
            
            success_count = sum(1 for b in branches if b.status == "success")
            return QueryDecompositionRun(
                enabled=True, round1_status="success", model=self.model, base_url=self.base_url,
                branches=branches, partial_success=0 < success_count < len(branches),
                round1_output=round1_data, error=None if success_count > 0 else "All branches failed"
            )
        except Exception as exc:
            return QueryDecompositionRun(enabled=True, round1_status="failed", model=self.model, 
                                       base_url=self.base_url, branches=[], error=str(exc))

    def _run_round1(self, query_text: str) -> dict[str, Any]:
        """Runs Stage 1 decomposition using JSON mode and Pydantic validation."""
        messages = [
            {"role": "system", "content": "You are a senior CS/AI research orchestrator. Return JSON only."},
            {"role": "user", "content": f"{self.round1_prompt_template}\n\nUser query: {query_text}"}
        ]
        raw = self._chat_completion(messages, json_mode=True)
        validated = Round1Response.model_validate_json(raw)
        
        # Deduplicate and truncate to max_directions
        unique = []
        seen = set()
        for d in validated.directions:
            if d.lower() not in seen:
                seen.add(d.lower())
                unique.append(d)
        validated.directions = unique[:self.max_directions]
        
        return validated.model_dump()

    def _run_round2_parallel(self, query_text: str, round1_output: dict[str, Any]) -> list[QueryBranchResult]:
        """Runs Stage 2 query generation for each direction in parallel."""
        directions = round1_output.get("directions", [])
        if not directions:
            return [QueryBranchResult(branch_id="branch_0", status="failed", error="No directions found")]

        specs = [(f"branch_{i}", i, d) for i, d in enumerate(directions)]
        by_branch = {bid: QueryBranchResult(branch_id=bid, status="failed") for bid, _, _ in specs}

        with ThreadPoolExecutor(max_workers=min(len(specs), 10)) as executor:
            future_to_id = {
                executor.submit(self._run_round2_branch, bid, idx, txt, query_text, round1_output): bid 
                for bid, idx, txt in specs
            }
            for future in as_completed(future_to_id):
                bid = future_to_id[future]
                try:
                    by_branch[bid] = future.result()
                except Exception as exc:
                    by_branch[bid].error = str(exc)

        return [by_branch[bid] for bid, _, _ in specs]

    def _run_round2_branch(self, branch_id, direction_index, direction_text, query_text, round1_output) -> QueryBranchResult:
        """Generates an expert-level search query for a specific direction."""
        prompt = (f"{self.round2_prompt_template}\n\n"
                  f"Focus Direction: {direction_text}\n"
                  f"Original Query: {query_text}\n"
                  f"Full Context Analysis: {json.dumps(round1_output)}")
        
        messages = [
            {"role": "system", "content": "You are a search query synthesizer for CS researchers. Return JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            raw = self._chat_completion(messages, json_mode=True)
            validated = Round2Response.model_validate_json(raw)
            return QueryBranchResult(branch_id=branch_id, status="success", search_query=validated.search_query)
        except (ValidationError, Exception) as exc:
            return QueryBranchResult(branch_id=branch_id, status="invalid_output", error=str(exc))
