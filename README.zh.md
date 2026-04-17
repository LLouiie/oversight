# Oversight

[English](README.md)

## 环境

1. 在**仓库根目录**创建并激活 conda 环境，并安装 spaCy 模型：

```bash
conda env create -f environment.local.yml
conda activate oversight-local
python -m spacy download en_core_web_sm
```

2. 复制示例环境文件并按本机情况修改：

```bash
cp example.env .env
```

编辑 `.env` 中的路径、模型名、Agent 接口等。`LINEAR_RAG_*` 请使用**相对仓库根目录**的路径；启动后端时应在仓库根目录执行，以便正确找到 `data/` 与 `LinearRAG/`。

## 运行

**后端**（仓库根目录，已激活环境）：

```bash
conda activate oversight-local
python flask_app.py
```

端口由 `.env` 中的 `FLASK_PORT` 决定（见 `example.env`）；也可临时指定：`FLASK_PORT=5001 python flask_app.py`。

**前端：**

```bash
cd frontend
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001 npm run dev
```

`NEXT_PUBLIC_BACKEND_URL` 需与 Flask 监听地址一致。

**健康检查：**

```bash
curl http://127.0.0.1:5001/api/health
```

若 `.env` 里端口不是 `5001`，请改成对应端口。
