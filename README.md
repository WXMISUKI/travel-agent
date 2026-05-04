# 旅行规划智能体 (Travel Agent)
git push origin master && git push github master
基于 **豆包大模型（火山引擎 Ark）** 的智能旅行规划助手，支持天气查询、火车票查询、景点推荐、智能行程规划等功能。项目采用 LangChain/LangGraph 实现 Agent 编排，支持流式响应输出。

## 功能特性

| 功能 | 说明 | 数据来源 |
|------|------|----------|
| 🌤️ 天气查询 | 查询目的地15天天气预报 | Open-Meteo API (开源免费) |
| 🚄 火车票查询 | 查询12306火车票余票信息 | 12306 MCP 服务 |
| 🎯 景点推荐 | 推荐热门景点、网红打卡地、美食 | 百度搜索 API |
| 📅 智能行程规划 | 自动规划多步骤旅行方案 | LangGraph 工作流 |
| 🔍 降级策略 | 主工具失败时自动使用搜索兜底 | 百度搜索 |

## 技术栈

| 层级 | 技术 |
|------|------|
| **LLM** | Doubao (通过火山引擎 Ark 调用) |
| **Agent** | LangChain + LangGraph (ReAct + Plan 混合模式) |
| **Web** | FastAPI + SSE (服务端推送流式响应) |
| **前端** | HTML + CSS + JavaScript (原生) |
| **数据源** | Open-Meteo + 12306 MCP + 百度搜索 |

## 项目结构

```
travel-agent/
├── src/                          # 核心源代码
│   ├── main.py                   # FastAPI 入口，提供 REST API
│   ├── config.py                 # 配置管理 (环境变量加载)
│   ├── agent/                    # Agent 层
│   │   ├── graph.py              # LangGraph 流程定义
│   │   ├── tools.py              # LangChain Tools 定义
│   │   ├── planner.py            # 执行计划生成器
│   │   ├── smart_planner.py      # 智能规划器 (多意图支持)
│   │   ├── state.py              # 状态定义
│   │   └── react.py              # ReAct 模式实现
│   ├── skills/                   # Skills 层 (业务能力)
│   │   ├── weather.py            # 天气查询技能
│   │   ├── ticket.py             # 车票查询技能
│   │   └── attraction.py         # 景点查询技能
│   ├── llm/                      # LLM 客户端
│   │   ├── client.py             # 豆包客户端封装
│   │   └── prompts.py            # 提示词模板
│   ├── data_sources/             # 数据源适配器
│   │   ├── weather.py            # Open-Meteo API 封装
│   │   ├── mcp_client.py         # 12306 MCP 客户端
│   │   ├── train_ticket.py       # 火车票查询
│   │   └── baidu_search.py       # 百度搜索 API 封装
│   ├── models/                   # 数据模型
│   │   ├── travel.py             # 旅行相关模型
│   │   └── context.py            # 上下文模型
│   └── utils/                    # 工具函数
│       ├── logger.py             # 日志封装 (loguru)
│       └── cache.py              # 缓存工具
├── frontend/                     # 前端界面
│   ├── index.html                # 主页面
│   └── src/                      # 前端源码
├── mcps/12306-mcp/              # 12306 MCP 服务 (独立项目)
├── docs/                        # 项目文档
├── requirements.txt             # Python 依赖
├── .env                        # 环境变量 (本地配置)
└── .env.example                # 环境变量模板
```

## 快速开始

### 1. 环境准备

```bash
# 创建 Python 虚拟环境 (推荐使用 conda)
conda create -n travel-agent python=3.11 -y
conda activate travel-agent

# 或者使用 venv
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入必要的 API Key：

```env
# ============================================
# 豆包模型配置（火山引擎，必需）
# ============================================
ARK_API_KEY=your-ark-api-key-here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=your-endpoint-or-model-id

# ============================================
# 百度搜索 API (降级方案，可选)
# ============================================
BAIDU_SEARCH_API_KEY=your-baidu-api-key-here

# ============================================
# 12306 MCP 服务地址
# 如果不启动 MCP 服务，火车票查询将使用降级搜索
# ============================================
MCP_BASE_URL=http://localhost:8000

# 日志配置
LOG_LEVEL=INFO
CACHE_TTL=3600
```

### 3. 启动 12306 MCP 服务 (可选)

火车票查询需要 MCP 服务支持。如需此功能，请参考 `mcps/12306-mcp/README.md` 启动服务。

> **注意**: 如果不启动 MCP 服务，火车票查询将自动降级使用百度搜索。

### 4. 启动后端

```bash
# 进入项目目录
cd travel-agent

# 启动 FastAPI 服务
uvicorn src.main:app --reload --port 8000

# 服务启动后访问:
# - API 文档: http://localhost:8000/docs
# - 健康检查: http://localhost:8000/health
```

### 5. 启动前端

```bash
# 方式1: 直接用浏览器打开 frontend/index.html

# 方式2: 使用 Python 内置服务器
cd frontend
python -m http.server 5173

# 方式3: 使用 Node.js (如果已安装)
npx http-server frontend -p 5173
```

然后访问 http://localhost:5173

## 使用示例

### 天气查询
```
用户：上海后天天气怎么样
助手：上海后天天气预报：
      🌤️ 天气：晴
      🌡️ 温度：18°C - 25°C
      💨 风速：12 km/h
      
      未来几天以晴好天气为主，适合出行！
```

### 火车票查询
```
用户：帮我查一下明天北京到上海的高铁
助手：为您查到以下高铁车次 (2026-03-15)：
      
      🚄 G1   北京南 → 上海虹桥   09:00 - 13:28   ¥553
      🚄 G3   北京南 → 上海虹桥   13:30 - 18:02   ¥553
      🚄 G5   北京南 → 上海虹桥   15:00 - 19:32   ¥553
      ...
```

### 景点推荐
```
用户：上海有什么好玩的地方
助手：为您推荐上海热门景点：
      
      🏛️ 外滩 - 观赏浦江两岸夜景
      🏰 上海迪士尼乐园 - 主题乐园
      🛕 豫园 - 江南园林代表
      🏢 东方明珠 - 上海地标建筑
      ...
```

### 智能行程规划
```
用户：我想去舟山玩，帮我规划一下
助手：为您规划舟山旅行方案：
      
      📅 建议行程：2-3天
      
      🌤️ 天气提示：
      - 近期以晴好天气为主
      - 建议携带轻便衣物
      
      🎯 推荐景点：
      - 桃花岛 - 金庸笔下的侠客胜地
      - 普陀山 - 佛教圣地
      - 东极岛 - 第一缕阳光
      
      💰 预算建议：500-1000元/天
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径，返回服务信息 |
| `/health` | GET | 健康检查 |
| `/chat` | POST | 普通聊天 (非流式) |
| `/chat/stream` | POST | 流式聊天 (推荐，使用 SSE) |
| `/tools` | GET | 获取可用工具列表 |

### 流式响应格式 (SSE)

```json
{"type": "start"}
{"type": "thinking", "content": ["🧠 分析需求..."]}
{"type": "todo", "items": ["⬜ [1] get_weather: 查询上海天气"]}
{"type": "step_status", "step_id": "1", "status": "running", "tool": "get_weather"}
{"type": "step_status", "step_id": "1", "status": "completed", "result": {...}}
{"type": "content", "content": "上海后天天气..."}
{"type": "done"}
```

## 开发指南

### 添加新工具

1. 在 `src/agent/tools.py` 中添加工具函数
2. 在 `AVAILABLE_TOOLS` 字典中注册工具
3. 在 `src/agent/planner.py` 的工具说明中添加工具描述

### 修改 Agent 逻辑

核心逻辑在 `src/agent/graph.py` 的 `TravelAgent` 类：
- `_parse_intent()` - 意图解析
- `create_execution_plan()` - 计划生成
- `execute_plan()` - 计划执行
- `_make_response()` - 响应生成

## 注意事项

1. **API Key 必需** - 首次使用需要配置豆包 API Key（火山引擎 Ark）
2. **MCP 服务** - 火车票查询需要先启动 12306 MCP 服务 (可选)
3. **天气查询** - 仅支持国内部分大城市
4. **降级策略** - 主工具失败时自动使用百度搜索兜底

## 常见问题

### Q: 如何获取豆包 API Key?
A: 访问火山引擎 Ark 控制台，创建 API Key 与模型接入点后填入 `.env`。

### Q: 火车票查询失败怎么办?
A: 确保 12306 MCP 服务已启动。如果无法启动，工具会自动降级使用百度搜索。

### Q: 天气查询支持哪些城市?
A: 支持 Open-Meteo API 覆盖的城市，主要包括省会城市和热门旅游城市。

## License

MIT License

---

** enjoying your travels! ✈️🌴
