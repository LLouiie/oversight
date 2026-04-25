<div align="center">
  <h1 style="font-size: 2.5em; line-height: 1.2; margin: 0.2em 0; border: none; padding: 0;">Multihop Oversight</h1>
</div>

Multihop Oversight extends the original [Oversight](https://github.com/ottowhite/oversight) paper search stack. To support **multihop** questions, we add a **query-decomposition agent** that splits the user query into **subqueries**, wire retrieval through **[LinearRAG](LinearRAG/)** (graph-based RAG over passages and entities), and add a **reranker** to rescore and reorder candidates.

## System overview

- **Inherits from Oversight** — the same `data/` paper corpus, Flask search API, and Next.js front end as the upstream project. Multihop behavior is added **on top of** that baseline.
- **Subquery agent** — an LLM-backed **query-decomposition** step (`oversight/query_decomposition_agent.py`) turns one user question into **subqueries** you can run sequentially or in combination for multihop coverage (OpenAI by default, or a local OpenAI-compatible server; see `example.env`).
- **LinearRAG** — subqueries (and the original query) drive **[LinearRAG](LinearRAG/)** retrieval: dense passage, sentence, and entity encodings plus a **knowledge graph** for graph-aware search over the corpus.
- **Reranker** — an optional **BGE** cross-encoder pass (`OVERSIGHT_RERANK_*` in `example.env`) rescores candidates so the final list better matches the full multihop intent.

**Request path (simplified):** `user query → decomposition agent → subqueries → LinearRAG retrieval → (optional) reranker → results`.

---

## Video comparison

The screen recording **compares the upstream [Oversight](https://github.com/ottowhite/oversight) interface with Multihop Oversight** (this repo) on the same or similar multihop-style queries, so you can see how subquery decomposition, LinearRAG retrieval, and reranking change the result quality and flow.

<video width="100%" controls playsinline>
  <source src="https://github.com/user-attachments/assets/ace0f3f5-d9fd-429a-b3f8-768a4b121b81" type="video/quicktime" />
</video>

[Direct link to video](https://github.com/user-attachments/assets/ace0f3f5-d9fd-429a-b3f8-768a4b121b81)

---

## How LinearRAG data is generated

**LinearRAG** is the retrieval core used **after** the subquery agent. The paper corpus (same layout as upstream Oversight) must be **indexed** into three embedding stores (passage, entity, sentence) and a **knowledge graph** before (or on first) search. That index is what each subquery hits during graph-based RAG. The pipeline can run on the **first** backend search request, or you can pre-build it offline.

### Data sources

Raw paper records live in `data/` as JSON arrays, one file per venue and year (e.g. `data/systems_conferences/osdi24.json`). Each record contains at minimum: `title`, `abstract`, `date`, and optionally `link` and `conference_name`. Papers from VLDB are scraped separately via `agent_scrapers/vldb_scraper.py`.

### Indexing pipeline (automatic on first request)

When `flask_app.py` receives the first search, `LinearRAGSearchEngine` runs `LinearRAG.index()`:

1. **NER** — spaCy (`en_core_web_sm` by default) extracts named entities from every passage and its constituent sentences. Results are cached in `LinearRAG/import/oversight_data/ner_results.json` so subsequent restarts skip already-processed passages.
2. **Embedding** — `SentenceTransformer` encodes passages, sentences, and entities into dense vectors. Each store is persisted as a Parquet file:
   - `passage_embedding.parquet`
   - `sentence_embedding.parquet`
   - `entity_embedding.parquet`
3. **Graph construction** — an `igraph` undirected graph is built from entity→passage and entity→sentence co-occurrence edges, plus adjacent-passage edges. The graph is optionally exported to `LinearRAG.graphml` for inspection.

These files live under `LinearRAG/import/oversight_data/`, are **ignored by git** (see `.gitignore`), and are produced on the **first** search request (or when you rebuild the index below). Fresh clones index automatically on first use.

### Re-generating from scratch

To rebuild the index from the raw JSON data (e.g. after adding new papers):

```bash
# Delete cached stores so the pipeline runs fresh
rm LinearRAG/import/oversight_data/ner_results.json
rm LinearRAG/import/oversight_data/*.parquet
# Restart the backend — indexing runs automatically on the first request
python flask_app.py
```

---

## Setup

1. **Python 3.10+**, install dependencies from the repository root (includes LinearRAG, the query agent client, the reranker stack, and the web app):

   ```bash
   uv sync
   # or: pip install -e .
   ```

2. **Download the spaCy model:**

   ```bash
   python -m spacy download en_core_web_sm
   ```

3. **Create your env file** (`.env` is gitignored — never commit real secrets):

   ```bash
   cp example.env .env
   ```

   Configure **(i)** LinearRAG data paths and embedding model (`LINEAR_RAG_*`), **(ii)** the **subquery** LLM (`OPENAI_*` or `LOCAL_AGENT_LLM_*` when `QUERY_DECOMPOSITION_AGENT_MODE=local`), and **(iii)** the optional **reranker** (`OVERSIGHT_RERANK_*`). Highlights:

   | Variable | Description |
   |----------|-------------|
   | `OPENAI_API_KEY` | Required for **openai** mode — subquery decomposition. |
   | `OPENAI_MODEL` | Chat model for the agent (default: `gpt-4o`). |
   | `QUERY_DECOMPOSITION_AGENT_MODE` | `openai` (default) or `local` (self-hosted vLLM, etc.). |
   | `LINEAR_RAG_DATA_DIR` / `LINEAR_RAG_*` | Corpus and LinearRAG working paths; embedding and NER model names. |
   | `OVERSIGHT_RERANK_ENABLED` | `true` / `false` — BGE reranker after LinearRAG retrieval. |
   | `FLASK_PORT` | Backend port (default: `5001`). |

   For a local subquery LLM, set `QUERY_DECOMPOSITION_AGENT_MODE=local` and `LOCAL_AGENT_LLM_BASE_URL`, `LOCAL_AGENT_LLM_MODEL`, `LOCAL_AGENT_LLM_API_KEY`. Full defaults and comments are in `example.env`.

---

## Run

With the stack running, a search request follows the path **agent (subqueries) → LinearRAG → reranker (if enabled)**.

**Backend** (from the repository root):

> **macOS note:** export `KMP_DUPLICATE_LIB_OK=TRUE` before starting Python to avoid a crash from duplicate OpenMP runtimes (PyTorch + sentence-transformers + the reranker). Other threading variables are set at the top of `flask_app.py`.

```bash
export KMP_DUPLICATE_LIB_OK=TRUE
python flask_app.py
```

**Frontend:**

```bash
cd frontend
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
```

**Health check:**

```bash
curl http://127.0.0.1:5001/api/health
```

**One-command start** (backend + frontend, see `start_oversight.sh` for details):

```bash
./start_oversight.sh up
```

---

## Benchmark (optional)

`benchmark/` holds **multihop**-style evaluation queries and ground truth (n0 / n1 / n2). Use it to measure LinearRAG (+ agent + optional rerank) against labels — not required for the web UI.

```bash
# Run eval on n0 / n1 / n2; writes results to benchmark/linear_rag_results/
python scripts/eval/run_final_query_2602_linear_rag.py

# Recompute metrics from multihop ground truth (reads benchmark/.../groundtruth/)
python scripts/eval/multi_hop_recompute.py
```

See `python scripts/eval/run_final_query_2602_linear_rag.py --help` for flags such as `--limit`, `--rerank`, and `--fuzzy-titles` (mirrors the rerank stage in the app).
