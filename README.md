# Oversight Submit Branch

这个分支只保留投稿/演示需要的主搜索链路：
- Flask API
- Query Decomposition Agent
- LinearRAG 检索（数据来自 `data/`）
- Cross-Encoder rerank

旧的 `pgvector/Postgres` 检索、mail/digest/sync、作者页和 Streamlit 入口都已经移除。

## 1. 创建并激活环境

```bash
cd /Users/lexi/workplace/oversight
conda env create -f environment.local.yml
conda activate oversight-local
python -m spacy download en_core_web_sm
```

## 2. 配置环境变量

LinearRAG 必需：

```env
LINEAR_RAG_DATA_DIR=/Users/lexi/workplace/oversight/data
LINEAR_RAG_ROOT=/Users/lexi/workplace/oversight/LinearRAG
LINEAR_RAG_WORKING_DIR=/Users/lexi/workplace/oversight/LinearRAG/import
LINEAR_RAG_DATASET_NAME=oversight_data
LINEAR_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
LINEAR_RAG_SPACY_MODEL=en_core_web_sm
LINEAR_RAG_MAX_WORKERS=1
```

Agent 示例：

```env
LOCAL_AGENT_ENABLED=true
LOCAL_AGENT_DEBUG=true
QUERY_DECOMPOSITION_AGENT_MODE=local
LOCAL_AGENT_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_AGENT_LLM_MODEL=Qwen/Qwen3-8B-Instruct
LOCAL_AGENT_LLM_API_KEY=local-dev-key
LOCAL_AGENT_LLM_TIMEOUT_SECONDS=20
```

Rerank 可选：

```env
OVERSIGHT_RERANK_ENABLED=true
OVERSIGHT_RERANK_MODEL=BAAI/bge-reranker-base
OVERSIGHT_RERANK_FP16=true
OVERSIGHT_RERANK_MAX_INPUT=60
```

## 3. 启动

后端：

```bash
conda activate oversight-local
cd /Users/lexi/workplace/oversight
FLASK_PORT=5001 python flask_app.py
```

前端：

```bash
conda activate oversight-local
cd /Users/lexi/workplace/oversight/frontend
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
```

健康检查：

```bash
curl http://127.0.0.1:5001/api/health
```

## 4. API

保留接口：
- `GET /api/health`
- `POST /api/search`

`/api/search` 示例：

```json
{
  "text": "rdma scheduling system",
  "time_window_days": 1825,
  "limit": 10,
  "rerank": true,
  "sources": {
    "OSDI": true,
    "NSDI": true,
    "ATC": true
  }
}
```

返回结构：

```json
{
  "results": [],
  "query_groups": [],
  "agent": {
    "enabled": true,
    "round1_status": "success",
    "partial_success": false
  }
}
```
