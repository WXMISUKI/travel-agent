# 旅行规划智能体 (Travel Agent)

基于 MiniMax 大模型的智能旅行规划助手，支持天气查询、火车票查询、景点推荐等功能。

## 功能特性

- ✅ 天气查询 - 基于 Open-Meteo 开源API
- ✅ 火车票查询 - 基于 12306 MCP 服务
- ✅ 景点美食搜索 - 基于百度搜索 API
- ✅ 智能行程规划 - LangChain Agent
- ✅ Web 前端界面 - Vue3 + 流式响应
- ✅ 降级策略 - 百度搜索兜底

## 技术栈

| 模块 | 技术 |
|------|------|
| LLM | MiniMax M2.5 (DashScope) |
| Agent | LangChain + LangGraph |
| Web | FastAPI + SSE |
| Frontend | HTML + CSS + JavaScript |
| 数据源 | Open-Meteo + 12306 MCP + 百度搜索 |

## 快速开始

### 1. 环境准备

```bash
# 创建 conda 环境
conda create -n travel-agent python=3.11 -y
conda activate travel-agent

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入您的 API Key：

```env
ORCH_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORCH_MODEL=MiniMax/MiniMax-M2.5
ORCH_API_KEY=your-api-key

BAIDU_SEARCH_API_KEY=your-baidu-api-key
MCP_BASE_URL=http://localhost:8000
```

### 3. 启动 12306 MCP 服务

参考 `mcps/12306-mcp` 文档启动 MCP 服务。

### 4. 启动后端

```bash
uvicorn src.main:app --reload --port 8000
```

### 5. 启动前端

直接用浏览器打开 `frontend/index.html`，或使用静态文件服务器：

```bash
# 使用 Python 内置服务器
cd frontend
python -m http.server 5173
```

然后访问 http://localhost:5173

## 项目结构

```
travel-agent/
├── src/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── agent/               # Agent 层
│   │   ├── graph.py         # LangGraph 流程
│   │   ├── tools.py         # LangChain Tools
│   │   └── state.py         # 状态定义
│   ├── skills/              # Skills 层
│   │   ├── weather.py      # 天气查询
│   │   ├── ticket.py       # 车票查询
│   │   └── attraction.py   # 景点查询
│   ├── llm/                 # LLM 客户端
│   ├── data_sources/        # 数据源适配器
│   └── models/              # 数据模型
├── frontend/                # 前端界面
├── requirements.txt         # Python 依赖
└── .env                     # 环境变量
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径 |
| `/health` | GET | 健康检查 |
| `/chat` | POST | 普通聊天 |
| `/chat/stream` | POST | 流式聊天 |
| `/tools` | GET | 工具列表 |

## 使用示例

```
用户：帮我查一下后天北京到上海的高铁
助手：为您查到以下高铁车次：
      G1   北京南 → 上海虹桥   09:00 - 13:28   ¥553
      G3   北京南 → 上海虹桥   13:30 - 18:02   ¥553
      ...

用户：上海后天天气怎么样
助手：上海后天天气：
      天气：晴
      温度：18°C - 25°C
      风速：12 km/h
      未来几天以晴好天气为主
```

## 注意事项

1. 首次使用需要配置 MiniMax API Key
2. 火车票查询需要先启动 12306 MCP 服务
3. 天气查询仅支持国内城市

## License

MIT