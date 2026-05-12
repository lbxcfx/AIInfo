# AIInfo 安装与启动说明

本项目当前在 WSL Ubuntu 下开发和运行。实际运行目录是：

```bash
/home/lbx/projects/AIInfo
```

## 1. 运行环境版本

当前开发环境版本：

```text
Python 3.12.3
Node.js v22.16.0
pnpm 10.23.0
```

前端关键依赖已固定在 `apps/web/package.json` 和 `pnpm-lock.yaml` 中：

```text
next 15.5.16
react 19.2.6
react-dom 19.2.6
eslint-config-next 15.5.16
```

后端 Python 依赖固定在 `apps/api/requirements.txt` 中。

## 2. 后端 requirements.txt

后端依赖安装命令：

```bash
cd /home/lbx/projects/AIInfo/apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

当前 `apps/api/requirements.txt` 固定版本如下：

```text
alembic==1.14.0
asyncpg==0.30.0
celery==5.4.0
fastapi==0.115.6
feedparser==6.0.11
httpx==0.28.1
meilisearch==0.31.6
openai==1.59.7
pgvector==0.3.6
psycopg[binary]==3.2.3
pydantic==2.10.4
pydantic-settings==2.7.1
pytest==8.3.4
pytest-asyncio==0.25.2
python-dotenv==1.0.1
redis==5.2.1
ruff==0.8.4
SQLAlchemy==2.0.36
trafilatura==2.0.0
uvicorn[standard]==0.34.0
```

## 3. 前端依赖安装

在项目根目录安装 pnpm 工作区依赖：

```bash
cd /home/lbx/projects/AIInfo
pnpm install --frozen-lockfile
```

如果修改过 `package.json`，需要重新生成锁文件：

```bash
cd /home/lbx/projects/AIInfo
pnpm install
```

## 4. 环境变量配置

从示例文件生成本地 `.env`：

```bash
cd /home/lbx/projects/AIInfo
cp .env.example .env
```

完整功能依赖以下本地服务：

```text
PostgreSQL: 127.0.0.1:5432
Redis: 127.0.0.1:6379
Meilisearch: http://127.0.0.1:7700
```

关键配置项：

```text
DATABASE_URL=postgresql+asyncpg://ai_intel:ai_intel_dev_password@127.0.0.1:5432/ai_intel_radar
DATABASE_SYNC_URL=postgresql+psycopg://ai_intel:ai_intel_dev_password@127.0.0.1:5432/ai_intel_radar
REDIS_URL=redis://127.0.0.1:6379/0
MEILISEARCH_URL=http://127.0.0.1:7700
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

只有需要 LLM 或外部平台能力时，才需要填写：

```text
ZAI_API_KEY
GITHUB_TOKEN
X_BEARER_TOKEN
```

## 5. 数据库迁移

PostgreSQL 启动后执行：

```bash
cd /home/lbx/projects/AIInfo/apps/api
source .venv/bin/activate
alembic upgrade head
```

## 6. 启动后端

前台启动：

```bash
cd /home/lbx/projects/AIInfo/apps/api
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

后台启动并写入日志：

```bash
cd /home/lbx/projects/AIInfo
mkdir -p .runtime
setsid -f bash -lc 'cd /home/lbx/projects/AIInfo/apps/api && source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload > /home/lbx/projects/AIInfo/.runtime/api.log 2>&1'
```

后端健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok","app":"ai-intel-radar","env":"development"}
```

## 7. 启动前端

如果 `3000` 端口空闲：

```bash
cd /home/lbx/projects/AIInfo
pnpm dev:web
```

如果 `3000` 已被占用，使用 `3002`：

```bash
cd /home/lbx/projects/AIInfo
pnpm --dir apps/web exec next dev -H 127.0.0.1 -p 3002
```

后台启动前端并写入日志：

```bash
cd /home/lbx/projects/AIInfo
mkdir -p .runtime
setsid -f pnpm --dir apps/web exec next dev -H 127.0.0.1 -p 3002 > .runtime/web-3002.log 2>&1 < /dev/null
```

浏览器访问：

```text
http://localhost:3002/
```

验证前端 CSS 是否正常加载：

```bash
curl -I http://127.0.0.1:3002/_next/static/css/app/layout.css
```

预期响应头：

```text
HTTP/1.1 200 OK
Content-Type: text/css; charset=UTF-8
```

## 8. 停止服务

```bash
pkill -f "uvicorn app.main:app"
pkill -f "next dev.*3002"
```

## 9. 验证命令

后端测试：

```bash
cd /home/lbx/projects/AIInfo/apps/api
source .venv/bin/activate
pytest
```

前端类型检查和构建：

```bash
cd /home/lbx/projects/AIInfo
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
```
