# Oversight

[中文说明](README.zh.md)

## Setup

1. From the **repository root**, create and activate the conda environment, then install the spaCy model:

```bash
conda env create -f environment.local.yml
conda activate oversight-local
python -m spacy download en_core_web_sm
```

2. Copy the example env file and edit it for your machine:

```bash
cp example.env .env
```

Open `.env` and change any paths, model names, or agent URLs you need. Keep `LINEAR_RAG_*` paths **relative to the repo root** and run the backend from that directory so `data/` and `LinearRAG/` resolve correctly.

## Run

**Backend** (repository root, env activated):

```bash
conda activate oversight-local
python flask_app.py
```

`FLASK_PORT` is read from `.env` (see `example.env`); override with `FLASK_PORT=5001 python flask_app.py` if needed.

**Frontend:**

```bash
cd frontend
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
```

Point `NEXT_PUBLIC_BACKEND_URL` at the same host/port as the Flask app.

**Health check:**

```bash
curl http://127.0.0.1:5001/api/health
```

(Use the port you set in `.env` if it is not `5001`.)
