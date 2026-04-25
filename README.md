# Oversight

A research paper search system built on [LinearRAG](LinearRAG/), combining graph-based retrieval with LLM-driven query decomposition.

---

## Demo

<video width="100%" controls playsinline>
  <source src="demo/oversight-demo.mov" type="video/quicktime" />
</video>

If the preview does not load in your browser, open the file in the repository: [`demo/oversight-demo.mov`](demo/oversight-demo.mov)

---

## How LinearRAG data is generated

The retrieval backend is powered by **LinearRAG**, a graph-based RAG pipeline. Before the system can answer queries, the paper corpus must be indexed into three embedding stores (passage, entity, sentence) and a knowledge graph. The pipeline runs automatically on the first search request, but can also be prepared offline.

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

The three Parquet files and `ner_results.json` are committed to the repository so the system starts immediately without re-indexing.

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

1. **Python 3.10+**, install dependencies from the repository root:

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

   Key variables to set in `.env`:

   | Variable | Description |
   |----------|-------------|
   | `OPENAI_API_KEY` | Required — used by the query decomposition agent. |
   | `OPENAI_MODEL` | Chat model (default: `gpt-4o`). |
   | `FLASK_PORT` | Backend port (default: `5001`). |
   | `QUERY_DECOMPOSITION_AGENT_MODE` | `openai` (default) or `local` (self-hosted vLLM etc.). |

   For a local LLM, set `QUERY_DECOMPOSITION_AGENT_MODE=local` and configure `LOCAL_AGENT_LLM_BASE_URL`, `LOCAL_AGENT_LLM_MODEL`, `LOCAL_AGENT_LLM_API_KEY`. All other variables have sensible defaults — see `example.env` for the full list.

---

## Run

**Backend** (from the repository root):

> **macOS note:** export `KMP_DUPLICATE_LIB_OK=TRUE` before starting Python to prevent a crash caused by duplicate OpenMP runtimes loaded by PyTorch and the reranker. All other threading variables are set automatically inside `flask_app.py`.

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

`benchmark/` contains evaluation queries and ground-truth labels. It is not required to run the web app.

```bash
# Run retrieval eval on n0 / n1 / n2 splits; writes results to benchmark/linear_rag_results/
python scripts/eval/run_final_query_2602_linear_rag.py

# Recompute metrics with multihop ground truth (reads benchmark/linear_rag_results/groundtruth/)
python scripts/eval/multi_hop_recompute.py
```

See `python scripts/eval/run_final_query_2602_linear_rag.py --help` for available flags (`--limit`, `--rerank`, `--fuzzy-titles`, etc.).
