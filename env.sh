#!/usr/bin/env bash

# Local agent (query decomposition) configuration
# Source this file before starting the Flask backend:
#   source ./env.sh
#
# Recommended local serving setup:
# - vLLM OpenAI-compatible server
# - BASE_URL should point to the /v1 prefix
#   e.g. http://127.0.0.1:8000/v1

if [ -z "${BASE_DIR:-}" ]; then
  if [ -n "${BASH_SOURCE[0]:-}" ]; then
    BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  else
    BASE_DIR="$(pwd)"
  fi
fi

export LINEAR_RAG_DATA_DIR="$BASE_DIR/data"
export LINEAR_RAG_ROOT="$BASE_DIR/LinearRAG"
export LINEAR_RAG_WORKING_DIR="$BASE_DIR/LinearRAG/import"
export LINEAR_RAG_DATASET_NAME="oversight_data"

export LOCAL_AGENT_ENABLED="${LOCAL_AGENT_ENABLED:-true}"
export LOCAL_AGENT_DEBUG="${LOCAL_AGENT_DEBUG:-true}"

# Select query decomposition agent backend mode:
# - local: use LOCAL_AGENT_LLM_* (e.g. vLLM on localhost)
# - remote: use API_URL/API_KEY (or REMOTE_AGENT_LLM_*) for remote OpenAI-compatible endpoints
export QUERY_DECOMPOSITION_AGENT_MODE="${QUERY_DECOMPOSITION_AGENT_MODE:-local}"

# OpenAI-compatible endpoint exposed by your local model server (e.g. vLLM)
export LOCAL_AGENT_LLM_BASE_URL="${LOCAL_AGENT_LLM_BASE_URL:-http://127.0.0.1:8000/v1}"

# Must match the model name served by vLLM
export LOCAL_AGENT_LLM_MODEL="${LOCAL_AGENT_LLM_MODEL:-Qwen/Qwen3-8B-Instruct}"

# vLLM often does not require a real API key; keep non-empty to satisfy clients if needed.
export LOCAL_AGENT_LLM_API_KEY="${LOCAL_AGENT_LLM_API_KEY:-local-dev-key}"

# Timeout per model call (seconds). Round 2 has 3 parallel calls using this timeout each.
export LOCAL_AGENT_LLM_TIMEOUT_SECONDS="${LOCAL_AGENT_LLM_TIMEOUT_SECONDS:-20}"

# Remote mode (OpenAI-compatible), e.g. DashScope compatible-mode endpoint
# These names are supported directly by the backend when QUERY_DECOMPOSITION_AGENT_MODE=remote
export API_URL="${API_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export API_KEY="${API_KEY:-}"

# Optional remote-specific overrides (if you want separate model/timeout for remote mode)
export REMOTE_AGENT_LLM_MODEL="${REMOTE_AGENT_LLM_MODEL:-${LOCAL_AGENT_LLM_MODEL}}"
export REMOTE_AGENT_LLM_TIMEOUT_SECONDS="${REMOTE_AGENT_LLM_TIMEOUT_SECONDS:-30}"
# export REMOTE_AGENT_LLM_BASE_URL="${REMOTE_AGENT_LLM_BASE_URL:-$API_URL}"
# export REMOTE_AGENT_LLM_API_KEY="${REMOTE_AGENT_LLM_API_KEY:-$API_KEY}"

# Round1 -> Round2 payload (for prompt authoring reference):
# - Original user query (verbatim)
# - Branch id: branch_0 … branch_{n-1} (n = number of directions from Round 1, capped by QUERY_DECOMPOSITION_MAX_DIRECTIONS)
# - Round 1 analysis JSON with normalized keys:
#   - intent: string
#   - keywords: string[]
#   - constraints: string[]
#   - facets: string[]
#   - notes: string[]
#   - directions: string[]   (model-chosen retrieval angles; one Round-2 call per entry)
#   - raw: object   (original Round 1 JSON before normalization)
# export QUERY_DECOMPOSITION_MAX_DIRECTIONS=16


export LOCAL_AGENT_ENABLED=true
export LOCAL_AGENT_DEBUG=true
export REMOTE_AGENT_LLM_TIMEOUT_SECONDS=60

# Example start commands (run manually in terminals, do not execute during `source`):
# FLASK_PORT=5001 python flask_app.py
# cd frontend && NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
