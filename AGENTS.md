# AGENTS.md - 旅行规划智能体项目指南

## 项目概述

这是一个基于 **MiniMax 大模型** 的智能旅行规划助手，支持天气查询、火车票查询、景点推荐等功能。项目采用模块化架构，使用 LangChain/LangGraph 实现 Agent 编排，支持流式响应输出。

### 技术栈

| 模块 | 技术 |
|------|------|
| LLM | MiniMax M2.5 (DashScope) |
| Agent | LangChain + LangGraph |
| Web | FastAPI + SSE (Server-Sent Events) |
| Frontend | HTML + CSS + JavaScript (原生) |
| 数据源 | Open-Meteo + 12306 MCP + 百度搜索 API |

---

## 项目结构

```
travel-agent/
├── src/                          # 核心源代码
│   ├── main.py                   # FastAPI 入口，提供 REST API
│   ├── config.py                 # 配置管理 (环境变量加载)
│   ├── agent/                    # Agent 层
│   │   ├── graph.py              # LangGraph 流程定义
│   │   ├── tools.py              # LangChain Tools 定义
│   │   ├── planner.py            # 执行计划生成器 (TODO系统)
│   │   ├── state.py               # 状态定义
│   │   ├── react.py               # ReAct 模式实现
│   │   └── tool_calling.py        # 工具调用逻辑
│   ├── skills/                   # Skills 层 (业务能力)
│   │   ├── weather.py            # 天气查询技能
│   │   ├── ticket.py             # 车票查询技能
│   │   ├── attraction.py         # 景点查询技能
│   │   └── base.py               # 技能基类
│   ├── llm/                      # LLM 客户端
│   │   ├── client.py             # MiniMax 客户端封装
│   │   └── prompts.py            # 提示词模板
│   ├── data_sources/             # 数据源适配器
│   │   ├── weather.py            # Open-Meteo API 封装
│   │   ├── mcp_client.py         # 12306 MCP 客户端
│   │   └── baidu_search.py       # 百度搜索 API 封装
│   ├── models/                   # 数据模型
│   │   ├── travel.py             # 旅行相关模型
│   │   └── context.py            # 上下文模型
│   └── utils/                    # 工具函数
│       ├── logger.py             # 日志封装 (loguru)
│       └── cache.py              # 缓存工具
├── frontend/                     # 前端界面
│   ├── index.html                # 主页面
│   ├── src/
│   │   ├── main.js               # 前端逻辑
│   │   ├── components/           # 组件
│   │   └── styles/               # 样式
│   └── package.json
├── mcps/12306-mcp/              # 12306 MCP 服务 (独立项目)
├── docs/                        # 项目文档
├── requirements.txt             # Python 依赖
├── .env                        # 环境变量 (本地配置)
└── .env.example                # 环境变量模板
```

---

## 快速启动

### 1. 环境准备

```bash
# 创建 conda 环境
conda create -n travel-agent python=3.11 -y
conda activate travel-agent

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入必要配置：

```env
# MiniMax 配置 (必需) - 通过阿里云 DashScope 获取
ORCH_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORCH_MODEL=MiniMax/MiniMax-M2.5
ORCH_API_KEY=your-api-key-here

# 百度搜索 API (降级方案)
BAIDU_SEARCH_API_KEY=your-baidu-api-key-here

# 12306 MCP 服务地址
MCP_BASE_URL=http://localhost:8000
```

### 3. 启动 12306 MCP 服务

```bash
cd mcps/12306-mcp
# 按照 mcps/12306-mcp/README.md 启动 MCP 服务
```

### 4. 启动后端

```bash
cd travel-agent
uvicorn src.main:app --reload --port 8000
```

### 5. 启动前端

```bash
# 方式1: 直接用浏览器打开 frontend/index.html
# 方式2: 使用 Python 内置服务器
cd frontend
python -m http.server 5173
# 访问 http://localhost:5173
```

---

## 核心模块说明

### Agent 架构 (src/agent/)

项目采用 **执行计划模式 (Planning Mode)**，核心流程：

1. **意图解析** - 分析用户查询，提取实体（出发地、目的地、日期）
2. **计划生成** - `planner.py` 生成 TODO 执行计划
3. **步骤执行** - 依次执行计划中的工具调用
4. **降级处理** - 主工具失败时使用百度搜索兜底
5. **响应生成** - LLM 根据查询结果生成最终回复

关键文件：
- `graph.py` - Agent 主类 `TravelAgent`，整合所有能力
- `planner.py` - `PlanGenerator` 和 `ExecutionPlan`，实现 TODO 计划系统
- `tools.py` - 工具函数定义（天气、火车票、景点等）

### 数据源 (src/data_sources/)

| 数据源 | 文件 | 说明 |
|--------|------|------|
| 天气 | `weather.py` | Open-Meteo 开源 API，无需 API Key |
| 火车票 | `mcp_client.py` | 调用 12306 MCP 服务 |
| 搜索 | `baidu_search.py` | 百度搜索 API，用于降级和景点搜索 |

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径，返回服务信息 |
| `/health` | GET | 健康检查 |
| `/chat` | POST | 普通聊天（非流式） |
| `/chat/stream` | POST | **流式聊天** (推荐) |
| `/tools` | GET | 获取可用工具列表 |

流式响应格式 (SSE)：
```json
{"type": "start"}
{"type": "thinking", "content": ["🧠 分析需求..."]}
{"type": "todo", "items": ["⬜ [1] get_station_by_city: 查找北京附近的火车站"]}
{"type": "step_status", "step_id": "1", "status": "running", "tool": "get_station_by_city"}
{"type": "step_status", "step_id": "1", "status": "completed", "result": {...}}
{"type": "content", "content": "为您查到..."}
{"type": "done"}
```

---

## 开发指南

### 添加新工具

1. 在 `src/agent/tools.py` 中添加工具函数
2. 在 `AVAILABLE_TOOLS` 字典中注册工具
3. 在 `src/agent/planner.py` 的 `TOOL_USAGES` 中添加工具说明

示例：
```python
# src/agent/tools.py
def my_new_tool(param: str) -> str:
    """工具描述"""
    # 实现逻辑
    return json.dumps(result, ensure_ascii=False)

AVAILABLE_TOOLS = {
    "my_new_tool": {
        "function": my_new_tool,
        "description": "工具描述。参数：param(参数说明)",
    }
}
```

### 添加新数据源

1. 在 `src/data_sources/` 目录创建新文件
2. 实现 API 封装类
3. 在 `src/agent/tools.py` 中添加调用逻辑

### 修改 Agent 逻辑

核心逻辑在 `src/agent/graph.py` 的 `TravelAgent` 类：
- `_parse_intent()` - 意图解析
- `create_execution_plan()` - 计划生成
- `execute_plan()` - 计划执行
- `_make_response()` - 响应生成

---

## 测试

项目包含测试文件在 `test/` 目录：

```bash
# 运行所有测试
python -m pytest test/

# 运行单个测试
python test/test_parse_date.py
python test/test_plan.py
```

---

## 注意事项

1. **API Key 必需** - 首次使用需要配置 MiniMax API Key (通过阿里云 DashScope)
2. **MCP 服务** - 火车票查询需要先启动 12306 MCP 服务
3. **天气查询** - 仅支持部分国内大城市
4. **降级策略** - 主工具失败时自动使用百度搜索兜底

---

## 日志

日志文件位于 `logs/travel-agent.log`，可通过 `.env` 中的 `LOG_LEVEL` 配置日志级别（默认 INFO）。
