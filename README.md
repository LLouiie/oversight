# Oversight

## Setup

1. **Python 3.10+** and a virtual environment (conda, `uv`, or `venv` are all fine).

2. **Install the project** from the repository root:

   ```bash
   uv sync
   # or: pip install -e .
   ```

3. **Download the spaCy model** used for LinearRAG (name must match `LINEAR_RAG_SPACY_MODEL` in your `.env`):

   ```bash
   python -m spacy download en_core_web_sm
   ```

4. **Create your local env file** (never commit real secrets; `.env` is gitignored):

   ```bash
   cp example.env .env
   ```

   Edit `.env` as described in [Environment variables](#environment-variables-from-exampleenv) below. Keep paths **relative to the repository root** for `LINEAR_RAG_*` and start the backend from the repo root so `data/` and `LinearRAG/` resolve correctly.

## Environment variables (from `example.env`)

`example.env` is a template. Copy it to `.env` and set values for your machine. The backend (`flask_app.py`) loads `.env` via [python-dotenv](https://pypi.org/project/python-dotenv/) at startup.

### How to use it

1. `cp example.env .env`
2. Change only what you need. Omitted keys fall back to defaults inside the code (not always the same as the example file for every variable).
3. **Paths**: with defaults, `LINEAR_RAG_DATA_DIR`, `LINEAR_RAG_ROOT`, and `LINEAR_RAG_WORKING_DIR` are **relative to the process working directory**. Run `python flask_app.py` from the **repository root** unless you set absolute paths.
4. **LLM for query decomposition**: set `QUERY_DECOMPOSITION_AGENT_MODE` to **`openai`** (default) for the OpenAI API (`OPENAI_API_KEY`, optional `OPENAI_BASE_URL` / `OPENAI_MODEL`, default model **`gpt-4o`**) or **`local`** for a self-hosted OpenAI-compatible server (e.g. vLLM) using `LOCAL_AGENT_LLM_*`.
5. **Frontend**: for `npm run dev` under `frontend/`, set `NEXT_PUBLIC_BACKEND_URL` in the shell (or a `frontend/.env.local`) to match the Flask port you use.

### Variable reference (same groupings as `example.env`)

| Variable | Role |
|----------|------|
| **LinearRAG** | |
| `LINEAR_RAG_DATA_DIR` | Data directory (default in code: `data` under repo). |
| `LINEAR_RAG_ROOT` | LinearRAG project root (default: `LinearRAG`). |
| `LINEAR_RAG_WORKING_DIR` | Import/build directory (default: `LinearRAG/import`). |
| `LINEAR_RAG_DATASET_NAME` | Dataset name under the import dir (e.g. `oversight_data`). |
| `LINEAR_RAG_EMBEDDING_MODEL` | Sentence-transformers model name for embeddings. |
| `LINEAR_RAG_SPACY_MODEL` | spaCy pipeline (install with `python -m spacy download ...`). |
| `LINEAR_RAG_MAX_WORKERS` | Worker threads for parts of the pipeline; keep small on laptops. |
| **Query decomposition agent** | |
| `LOCAL_AGENT_ENABLED` | `true` / `false` — enable the HTTP client to the LLM. |
| `LOCAL_AGENT_DEBUG` | Verbose logging for the agent. |
| `QUERY_DECOMPOSITION_AGENT_MODE` | **`openai`** (default): OpenAI API via `OPENAI_*`. **`local`**: self-hosted OpenAI-compatible server via `LOCAL_AGENT_LLM_*`. **`remote`**: legacy custom URL (`API_URL`, `REMOTE_AGENT_*`, etc.). |
| `OPENAI_API_KEY` | Required for **`openai`** mode (set in `.env`, never commit). |
| `OPENAI_BASE_URL` | Base URL (default in code: `https://api.openai.com/v1`). Use for Azure / proxies if needed. |
| `OPENAI_MODEL` | Chat model (default in code: **`gpt-4o`**). |
| `OPENAI_TIMEOUT_SECONDS` | Request timeout (seconds) for the agent. |
| `LOCAL_AGENT_LLM_BASE_URL` | For **`local`**: server base URL, e.g. `http://127.0.0.1:8000/v1`. |
| `LOCAL_AGENT_LLM_MODEL` | For **`local`**: model id on that server. |
| `LOCAL_AGENT_LLM_API_KEY` | For **`local`**: API key; use a dummy if the server does not check it. |
| `LOCAL_AGENT_LLM_TIMEOUT_SECONDS` | For **`local`**: request timeout in seconds. |
| **Optional rerank** | |
| `OVERSIGHT_RERANK_ENABLED` | `true` to load the cross-encoder reranker. |
| `OVERSIGHT_RERANK_MODEL` | Hugging Face model id (e.g. BGE reranker). |
| `OVERSIGHT_RERANK_FP16` | `true` / `false` for half precision where supported. |
| `OVERSIGHT_RERANK_MAX_INPUT` | Max number of candidate passages sent to the reranker. |
| **Backend** | |
| `FLASK_PORT` | HTTP port. `example.env` uses `5001` to match the frontend snippets; if unset, the app defaults to **5002**—set this variable to avoid mismatches. |
| `CORS_ORIGINS` | Comma-separated list of allowed browser origins (default includes `http://localhost:3000` for the Next.js dev server). |
| **Frontend (shell / `frontend/.env*`)** | |
| `NEXT_PUBLIC_BACKEND_URL` | Public URL of the Flask API, e.g. `http://127.0.0.1:5001`, must match the port in `FLASK_PORT`. |

### Optional / tuning (not in `example.env`)

| Variable | Role |
|----------|------|
| `LINEAR_RAG_RETRIEVAL_POOL_SIZE` | Pool size for retrieval (default in code: `120`). |
| `LINEAR_RAG_USE_VECTORIZED` | `true` / `false` for vectorized retrieval path. |
| `LINEAR_RAG_AGENT_BRANCH_LIMIT` | Cap on subquery branches (default `50`). |
| `LINEAR_RAG_DEVICE` | Device for some embedding paths (e.g. `cpu`). |
| `OVERSIGHT_RERANK_TOP_K` | How many results to keep after reranking. |
| `OVERSIGHT_FLASK_DEBUG` | `true` for Flask debug mode. |
| `OVERSIGHT_FLASK_RELOADER` | `true` to use the reloader. |
| `QUERY_DECOMPOSITION_MAX_DIRECTIONS` | Upper bound on decomposition directions. |
| `LINEAR_RAG` OpenAI vars | In **LinearRAG** scripts, `OPENAI_API_KEY` / `OPENAI_BASE_URL` may be read separately; the **Flask** query-decomposition agent uses the variables in the table above when `QUERY_DECOMPOSITION_AGENT_MODE=openai`. |

For **`remote`** and extra fallbacks, the app also accepts `API_URL`, `API_KEY`, `REMOTE_AGENT_LLM_BASE_URL`, etc. See `oversight/query_decomposition_agent.py` for resolution order.

## Run

**Backend** (repository root, virtual environment active):

```bash
python flask_app.py
```

**Frontend:**

```bash
cd frontend
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
```

Use the same port as `FLASK_PORT` in your `.env`.

**Health check:**

```bash
curl http://127.0.0.1:5001/api/health
```

Adjust the URL if you changed `FLASK_PORT`.

**Convenience script** (exports common vars and starts backend + frontend — see `start_oversight.sh` comments):

```bash
./start_oversight.sh up
```

## Benchmark (optional)

The **`benchmark/`** directory stores the evaluation queries and ground-truth keys (`sampled_multi_paper_entities_n0|n1|n2_output.json`) plus optional multihop overlap labels in `benchmark/linear_rag_results/groundtruth/`. It is **not** required to run the web app.

To run the same LinearRAG + query-decomposition stack as the API and write per-split eval JSONs and `linear_rag_eval_summary.json` under `benchmark/linear_rag_results/`, from the **repository root** (with `.env` configured for retrieval and the LLM):

```bash
python scripts/eval/run_final_query_2602_linear_rag.py
```

Useful flags: `--help`, `--limit`, `--rerank`, `--fuzzy-titles`, `--data-dir`, `--output-dir`. After you have `n0|n1|n2_linear_rag_eval.json`, optional multihop label recomputation: `python scripts/eval/multi_hop_recompute.py` (see script docstring; regenerates into `benchmark/linear_rag_results/recomputed_metrics/`, which is gitignored by default).

**Docker (optional):** see the `Makefile` and `docker-compose.yml` in the repository root.
