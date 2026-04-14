# Oversight 本地运行说明（简版）

这个项目当前后端搜索链路是：
- Flask API
- Query Decomposition Agent（可选）
- LinearRAG 检索（数据来自 `data/` 目录）

## 1. 创建并激活 conda 环境

```bash
cd /Users/lexi/workplace/oversight
conda env create -f environment.local.yml
conda activate oversight-local
```

> 建议 Node 使用 18（前端 Next 12 更稳定）：
```bash
conda install -n oversight-local -c conda-forge -y "nodejs=18.*"
```

安装 LinearRAG 额外依赖：

```bash
pip install sentence-transformers spacy python-igraph
python -m spacy download en_core_web_sm
```

## 2. 配置环境变量

可以写到 `.env`，也可以在终端 `export`。

### 2.1 LinearRAG 相关（必需）

```env
LINEAR_RAG_DATA_DIR=/Users/lexi/workplace/oversight/data
LINEAR_RAG_ROOT=/Users/lexi/workplace/oversight/LinearRAG
LINEAR_RAG_WORKING_DIR=/Users/lexi/workplace/oversight/LinearRAG/import
LINEAR_RAG_DATASET_NAME=oversight_data
LINEAR_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
LINEAR_RAG_SPACY_MODEL=en_core_web_sm
LINEAR_RAG_MAX_WORKERS=1
```

### 2.2 Agent 相关（可选）

如果不配，会显示 `Agent off / skipped`，搜索仍可用（只是不做 query decomposition）。

#### remote 模式示例

```env
LOCAL_AGENT_ENABLED=true
LOCAL_AGENT_DEBUG=true
QUERY_DECOMPOSITION_AGENT_MODE=remote
API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=你的key
REMOTE_AGENT_LLM_MODEL=qwen-max
REMOTE_AGENT_LLM_TIMEOUT_SECONDS=60
```

#### local 模式示例（本地 OpenAI-compatible 服务）

```env
LOCAL_AGENT_ENABLED=true
LOCAL_AGENT_DEBUG=true
QUERY_DECOMPOSITION_AGENT_MODE=local
LOCAL_AGENT_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_AGENT_LLM_MODEL=Qwen/Qwen3-8B-Instruct
LOCAL_AGENT_LLM_API_KEY=local-dev-key
LOCAL_AGENT_LLM_TIMEOUT_SECONDS=20
```

## 3. 启动后端

```bash
conda activate oversight-local
cd /Users/lexi/workplace/oversight

# 推荐固定关闭 Flask 自动重载，避免长检索中断
FLASK_PORT=5001 python flask_app.py
```

健康检查：

```bash
curl http://127.0.0.1:5001/api/health
```

> 注意：根路径 `/` 返回 404 是正常的，后端接口是 `/api/*`。

## 4. 启动前端

新开一个终端：

```bash
conda activate oversight-local
cd /Users/lexi/workplace/oversight/frontend
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
```

浏览器访问：

`http://localhost:3000`

## 5. 常见问题

1. `Agent not configured (base_url/model missing...)`
- 说明 agent 环境变量不完整。至少要配好 `base_url + model`（local 或 remote 二选一）。

2. 前端报 `ECONNREFUSED`
- 检查前端的 `NEXT_PUBLIC_BACKEND_URL` 端口是否和后端一致。

3. 前端报 `socket hang up / ECONNRESET`
- 通常是后端请求中断或重启。先看后端终端日志是否报错。

4. `TypeError ... jsonwebtoken ... prototype`
- 多数是 Node 版本过高导致。请用 Node 18。

## 6. Retrieval 返回格式与代码接口位置

### 6.1 前端调用的后端接口

- 接口：`POST /api/search`
- 文件：`flask_app.py`
- 入口函数：`search()`

示例请求：

```json
{
  "text": "rdma scheduling system",
  "time_window_days": 1825,
  "limit": 10,
  "sources": {
    "OSDI": true,
    "NSDI": true,
    "ATC": true
  }
}
```

字段说明：
- `text`: 检索文本（必填）
- `time_window_days`: 时间窗口（天），默认 5 年
- `limit`: 每个检索分支返回上限，默认 10
- `sources`: 来源过滤（会议/来源开关）

### 6.2 `/api/search` 返回结构

统一返回 JSON 结构如下：

```json
{
  "results": [
    {
      "paper_id": "...",
      "title": "...",
      "abstract": "...",
      "source": "OSDI",
      "link": "...",
      "paper_date": "2024-07-10"
    }
  ],
  "query_groups": [
    {
      "branch_id": "branch_0",
      "status": "success",
      "search_query": "...",
      "error": null,
      "results": []
    }
  ],
  "agent": {
    "enabled": true,
    "round1_status": "success",
    "partial_success": false,
    "model": "...",
    "base_url": "..."
  }
}
```

字段说明：
- `results`: 聚合去重后的扁平检索结果（前端主要显示这一层）
- `query_groups`: Agent 每个检索方向（`branch_0`…`branch_{n-1}`，由 Round 1 的 `directions` 数量决定）的详情
- `agent`: Agent 运行状态和元信息

### 6.3 代码位置（按职责）

- API 路由与响应组装：`flask_app.py`
  - `search()`：解析请求、调 agent、调 retrieval、组装响应
  - `_paper_to_api_dict()`：把 `Paper` 对象转成 API 返回字段
  - `_dedupe_flat_results()`：合并分支结果并按 `paper_id` 去重

- LinearRAG 检索接口：`linear_rag_search.py`
  - `LinearRAGSearchEngine.search_related_papers(...)`
    - 输入：`query_text/query_timedelta/selected_sources/limit`
    - 输出：`list[Paper]`
  - `_load_papers()`：从 `data/` 读取并标准化论文
  - `_paper_to_passage()`：转成 LinearRAG passage 文本

- Agent 接口：`query_decomposition_agent.py`
  - `QueryDecompositionAgent.decompose(...)`
  - 返回类型：`QueryDecompositionRun`（包含 `branches` 与 `agent_meta`）
