# Vercel 前后端一体部署指南

本项目已支持通过 Vercel 部署前端和 FastAPI 后端（Serverless）。

## 1. 代码准备

已包含以下关键文件：

- `vercel.json`：路由与函数配置
- `api/index.py`：Vercel Python 入口，暴露 `src.main:app`
- `.python-version`：固定 Python 运行时版本为 `3.11`

## 2. Vercel 项目设置

1. 在 Vercel 导入本仓库（Root Directory 选择仓库根目录）。
2. Framework Preset 选择 `Other`。
3. Build Command 留空（使用 Vercel Python Runtime）。
4. Output Directory 留空。

说明：
- 不要在 `vercel.json` 中给 Python 函数写 `"runtime": "python3.11"`，这会触发 `Function Runtimes must have a valid version`。
- 当前方案通过 `.python-version` 指定 Python 版本，通过 `functions` 中的 `maxDuration` 配置函数执行时长。
- `functions` 的匹配项使用精确路径 `api/index.py`，避免通配模式在 Vercel 构建阶段出现未匹配错误。

## 3. 环境变量（必须）

在 Vercel Project Settings -> Environment Variables 中配置：

- `LLM_PROVIDER=ark`
- `ARK_API_KEY=你的火山引擎 Key`
- `ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`
- `ARK_MODEL=你的模型或接入点`
- `BAIDU_SEARCH_API_KEY=你的百度搜索 key`（可选但建议）
- `MCP_BASE_URL=https://你的12306-mcp公网地址`
- `LOG_LEVEL=INFO`
- `CACHE_TTL=3600`
- `STREAM_DEBUG_DELAY_MS=0`
- `CORS_ALLOW_ORIGINS=https://your-app.vercel.app`
- `API_AUTH_ENABLED=true`
- `API_AUTH_KEY=你的高强度密钥`
- `API_AUTH_HEADER=x-api-key`

说明：
- 不要在 Vercel 使用本地地址（如 `http://localhost:8000`）作为 `MCP_BASE_URL`。
- `.env` 不会自动上传到 Vercel，必须在控制台配置环境变量。

## 4. 路由说明

`vercel.json` 已将以下路径映射到 FastAPI：

- `/chat/stream`
- `/chat/workflow`
- `/chat`
- `/health`
- `/tools`
- `/audit/*`

前端静态资源：

- 使用文件系统直接提供 `frontend/assets/*`
- `/` 返回 `frontend/index.html`
- 不再通过 rewrite 暴露 `frontend/src/*`

## 5. 生产注意事项（企业级）

1. SSE 与超时
- 当前 Serverless `maxDuration` 配置为 60 秒。
- `chat/stream` 为长连接接口，建议控制单次请求复杂度，避免超时。

2. 日志与审计
- Vercel 为无状态环境，本地持久化不可依赖。
- 项目已在 Vercel 环境将审计文件写入 `/tmp/logs`（临时存储）。
- 生产建议接入外部日志系统（如 Datadog、ELK、Sentry、Axiom）。

3. MCP 服务安全
- `MCP_BASE_URL` 指向公网时，必须增加鉴权（Token、签名、IP 白名单）。
- 建议 MCP 单独部署并限流，避免被滥用。

4. CORS
- 通过 `CORS_ALLOW_ORIGINS` 配置生产域名白名单，多个域名使用逗号分隔。

5. API 鉴权
- `/chat*` 与 `/audit*` 已支持 API Key 鉴权中间件。
- 开启方式：`API_AUTH_ENABLED=true` 且配置 `API_AUTH_KEY`。
- 请求头默认 `x-api-key`，可通过 `API_AUTH_HEADER` 修改。

6. 前端 API 地址
- 前端默认同源调用（线上不需要硬编码 API 域名）。
- 本地开发在 `localhost` 时自动使用 `http://localhost:8000`。
