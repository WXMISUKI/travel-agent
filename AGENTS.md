# AGENTS.md - 旅行规划智能体项目指南

## 项目概述

这是一个基于 **MiniMax 大模型** 的智能旅行规划助手，支持天气查询、火车票查询、景点推荐等功能。项目采用模块化架构，使用 LangChain/LangGraph 实现 Agent 编排，支持流式响应输出。

**核心特性：**
- 智能计划生成器（SmartPlanner）- 自动生成执行计划
- 时间上下文管理（TimeContext）- 智能日期解析与时间处理
- 降级策略 - 主工具失败时自动使用备用方案
- 审计日志系统 - 完整的会话追踪和性能监控
- LangGraph 工作流 - 状态机式流程编排

### 技术栈

| 模块 | 技术 |
|------|------|
| LLM | MiniMax M2.5 (DashScope) |
| Agent | LangChain + LangGraph |
| Web | FastAPI + SSE (Server-Sent Events) |
| Frontend | HTML + CSS + JavaScript (原生) |
| 数据源 | Open-Meteo + 12306 MCP + 百度搜索 API |
| 日志 | loguru + 自定义审计系统 |

---

## 项目结构

```
travel-agent/
├── src/                          # 核心源代码
│   ├── main.py                   # FastAPI 入口，提供 REST API
│   ├── config.py                 # 配置管理 (环境变量加载)
│   ├── agent/                    # Agent 层
│   │   ├── graph.py              # Agent 主类，整合所有能力
│   │   ├── tools.py              # LangChain Tools 定义
│   │   ├── planner.py            # 执行计划生成器 (兼容层)
│   │   ├── smart_planner.py      # 智能计划生成器 (核心)
│   │   ├── state.py              # 状态定义
│   │   ├── time_context.py       # 时间上下文管理
│   │   ├── workflow.py           # LangGraph 工作流
│   │   ├── gen_agent_graph.py    # 生成智能体图
│   │   └── visualize_agent.py    # 智能体可视化
│   ├── skills/                   # Skills 层 (业务能力)
│   │   ├── weather.py            # 天气查询技能
│   │   ├── ticket.py             # 车票查询技能
│   │   ├── attraction.py         # 景点查询技能
│   │   └── base.py               # 技能基类
│   ├── llm/                      # LLM 客户端
│   │   ├── client.py             # MiniMax 客户端封装
│   │   └── prompts.py            # 提示词模板
│   ├── data_sources/             # 数据源适配器
│   │   ├── weather.py            # 天气数据源
│   │   ├── weather_api.py        # Open-Meteo API 封装
│   │   ├── mcp_client.py         # 12306 MCP 客户端
│   │   ├── train_ticket.py       # 火车票数据源
│   │   ├── flight.py             # 航班数据源
│   │   ├── nearby.py             # 附近信息数据源
│   │   └── baidu_search.py       # 百度搜索 API 封装
│   ├── models/                   # 数据模型
│   │   ├── travel.py             # 旅行相关模型
│   │   └── context.py            # 上下文模型
│   └── utils/                    # 工具函数
│       ├── logger.py             # 日志封装 (loguru)
│       ├── cache.py              # 缓存工具
│       ├── audit_logger.py       # 审计日志系统
│       └── visualize.py          # 可视化工具
├── frontend/                     # 前端界面
│   ├── index.html                # 主页面
│   ├── src/
│   │   ├── main.js               # 前端逻辑
│   │   ├── components/           # 组件
│   │   └── styles/               # 样式
│   └── package.json
├── mcps/12306-mcp/              # 12306 MCP 服务 (独立项目)
├── docs/                        # 项目文档
├── test/                        # 测试文件
│   ├── test_parse_date.py       # 日期解析测试
│   ├── test_plan.py             # 计划生成测试
│   ├── test_station.py          # 站点查询测试
│   ├── test_train_api.py        # 火车票 API 测试
│   ├── test_weather_api.py      # 天气 API 测试
│   └── test_weather.py          # 天气查询测试
├── logs/                        # 日志目录
├── requirements.txt             # Python 依赖
├── start.bat                    # Windows 启动脚本
├── .env                        # 环境变量 (本地配置)
└── .env.example                # 环境变量模板
```

---

## 快速启动

### 1. 环境准备

```bash
# 创建 conda 环境
conda create -n langgraph-env python=3.11 -y
conda activate langgraph-env

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入必要配置：

```env
# MiniMax 配置（必需）
# 通过阿里云 DashScope 获取：https://dashscope.console.aliyun.com/
ORCH_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORCH_MODEL=MiniMax/MiniMax-M2.5
ORCH_API_KEY=your-api-key-here

# 百度搜索 API（降级方案）
BAIDU_SEARCH_API_KEY=your-baidu-api-key-here

# 12306 MCP 服务地址
MCP_BASE_URL=http://localhost:8000

# 日志配置
LOG_LEVEL=INFO

# 缓存配置（秒）
CACHE_TTL=3600
```

### 3. 启动 12306 MCP 服务

```bash
cd mcps/12306-mcp
# 按照 mcps/12306-mcp/README.md 启动 MCP 服务
```

### 4. 启动后端

**方式1：使用启动脚本（Windows）**
```bash
start.bat
```

**方式2：手动启动**
```bash
# 激活环境
conda activate langgraph-env

# 启动服务
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后，访问 http://localhost:8000 查看 API 文档

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

项目采用 **智能计划模式 (Smart Planning Mode)**，核心流程：

1. **意图解析** - 使用 `SmartPlanner` 分析用户查询，提取实体（出发地、目的地、日期）
2. **计划生成** - `smart_planner.py` 生成智能执行计划，包含步骤和降级策略
3. **时间上下文** - `time_context.py` 智能解析日期（"明天"、"下周五"等）
4. **步骤执行** - 依次执行计划中的工具调用，支持参数修复和降级
5. **审计追踪** - `audit_logger.py` 记录完整执行过程
6. **响应生成** - LLM 根据查询结果生成最终回复

关键文件：
- `graph.py` - Agent 主类 `TravelAgent`，整合所有能力
- `smart_planner.py` - `SmartPlanner`，智能计划生成器（核心）
- `planner.py` - 兼容层，支持旧版计划系统
- `time_context.py` - 时间上下文管理，日期解析和格式化
- `workflow.py` - LangGraph 工作流实现
- `tools.py` - 工具函数定义（天气、火车票、景点等）
- `gen_agent_graph.py` - 生成智能体可视化图
- `visualize_agent.py` - 智能体架构可视化工具

### 数据源 (src/data_sources/)

| 数据源 | 文件 | 说明 |
|--------|------|------|
| 天气 | `weather.py`, `weather_api.py` | Open-Meteo 开源 API，无需 API Key |
| 火车票 | `mcp_client.py`, `train_ticket.py` | 调用 12306 MCP 服务 |
| 航班 | `flight.py` | 航班数据源（预留） |
| 附近 | `nearby.py` | 附近信息查询（预留） |
| 搜索 | `baidu_search.py` | 百度搜索 API，用于降级和景点搜索 |

### 工具函数 (src/utils/)

| 工具 | 文件 | 说明 |
|------|------|------|
| 日志 | `logger.py` | 基于 loguru 的日志封装 |
| 缓存 | `cache.py` | 内存缓存工具 |
| 审计 | `audit_logger.py` | 审计日志系统，追踪会话和性能 |
| 可视化 | `visualize.py` | 数据可视化工具 |

### API 接口

#### 基础接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径，返回服务信息和版本 |
| `/health` | GET | 健康检查，返回当前日期 |
| `/chat` | POST | 普通聊天（非流式） |
| `/chat/stream` | POST | **流式聊天** (推荐) |
| `/chat/workflow` | POST | LangGraph 工作流聊天接口 |
| `/tools` | GET | 获取可用工具列表 |

#### 审计接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/audit/session/{session_id}` | GET | 获取会话审计信息 |
| `/audit/metrics` | GET | 获取性能指标（默认24小时） |
| `/audit/events` | GET | 查询审计事件（支持过滤） |

#### 流式响应格式 (SSE)

```json
{"type": "start", "session_id": "abc123"}
{"type": "thinking", "content": ["🧠 分析需求...", "📅 当前日期: 2026-04-08"]}
{"type": "todo", "items": ["⬜ [1] parse_date: 解析日期", "⬜ [2] get_weather: 查询天气"]}
{"type": "step_status", "step_id": "1", "status": "running", "tool": "parse_date"}
{"type": "step_status", "step_id": "1", "status": "completed", "result": {"parsed": "2026-04-09"}}
{"type": "step_status", "step_id": "2", "status": "completed", "result": {...}}
{"type": "content", "content": "为您查到..."}
{"type": "done", "session_id": "abc123"}
```

步骤状态类型：
- `running` - 步骤正在执行
- `completed` - 步骤成功完成
- `fallback_success` - 降级成功
- `failed` - 步骤失败
- `error` - 步骤异常

---

## 开发指南

### 添加新工具

1. 在 `src/agent/tools.py` 中添加工具函数
2. 在 `AVAILABLE_TOOLS` 字典中注册工具
3. （可选）在 `src/agent/smart_planner.py` 的工具列表中添加描述

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
- `_parse_intent()` - 意图解析（兼容层）
- `_make_response()` - 响应生成
- `_make_response_from_smart_plan()` - 从智能计划生成响应
- `_call_with_fallback()` - 带降级的工具调用

### 使用智能计划生成器

```python
from src.agent.smart_planner import get_smart_planner

planner = get_smart_planner()
plan = planner.generate_plan("明天北京到上海的火车票")

# plan 包含：
# - intent: 意图类型
# - entities: 提取的实体
# - steps: 执行步骤列表
# - fallback_plan: 降级计划
```

### 使用时间上下文

```python
from src.agent.time_context import get_time_context

time_ctx = get_time_context()
time_ctx.refresh()  # 刷新当前时间

# 解析日期
parsed_date = time_ctx.parse_natural_date("后天")
weekday = time_ctx.get_weekday_name("2026-04-08")
```

### 使用审计日志

```python
from src.utils.audit_logger import get_audit_logger, EventType

audit = get_audit_logger()

# 记录事件
audit.log_user_query("session_id", "用户消息")
audit.log_tool_call("session_id", "tool_name", {"param": "value"})
audit.log_response("session_id", "响应内容", success=True)

# 查询事件
events = audit.query_events(session_id="session_id", limit=10)
metrics = audit.get_metrics_summary(hours=24)
```

---

## 测试

项目包含测试文件在 `test/` 目录：

```bash
# 运行所有测试
python -m pytest test/

# 运行单个测试
python test/test_parse_date.py       # 日期解析测试
python test/test_plan.py            # 计划生成测试
python test/test_station.py         # 站点查询测试
python test/test_train_api.py       # 火车票 API 测试
python test/test_weather_api.py     # 天气 API 测试
python test/test_weather.py         # 天气查询测试
```

---

## 注意事项

1. **API Key 必需** - 首次使用需要配置 MiniMax API Key (通过阿里云 DashScope)
2. **MCP 服务** - 火车票查询需要先启动 12306 MCP 服务
3. **天气查询** - 仅支持部分国内大城市
4. **降级策略** - 主工具失败时自动使用百度搜索兜底
5. **环境名称** - conda 环境名称为 `langgraph-env`
6. **Python 版本** - 建议使用 Python 3.11
7. **审计日志** - 默认启用，记录所有会话和工具调用

---

## 日志

### 应用日志

日志文件位于 `logs/travel-agent.log`，可通过 `.env` 中的 `LOG_LEVEL` 配置日志级别（默认 INFO）。

### 审计日志

审计日志位于 `logs/` 目录：
- `audit.log` - 审计事件日志
- `metrics.log` - 性能指标日志
- `traces.log` - 执行追踪日志

可通过 API 接口查询审计数据：
- `/audit/session/{session_id}` - 查看会话详情
- `/audit/metrics` - 查看性能指标
- `/audit/events` - 查询审计事件

---

## 可视化

### 智能体架构图

生成智能体架构可视化图：

```bash
python -m src.agent.gen_agent_graph
```

生成的图片保存在项目根目录。

### 工作流可视化

项目包含 LangGraph 工作流的可视化图：
- `langgraph_workflow.png` - 工作流流程图
- `langgraph_full_agent.png` - 完整智能体架构图

---

## 常见问题

### Q: 火车票查询失败怎么办？

A: 系统会自动降级到百度搜索。如需完整功能，请确保：
1. 12306 MCP 服务已启动
2. MCP_BASE_URL 配置正确

### Q: 日期解析不准确？

A: 时间上下文系统支持自然语言日期，如"明天"、"下周五"等。确保：
1. 系统时间设置正确
2. 使用中文日期表达

### Q: 如何查看审计信息？

A: 访问审计接口：
```bash
# 查看性能指标
curl http://localhost:8000/audit/metrics

# 查看会话详情
curl http://localhost:8000/audit/session/{session_id}
```

### Q: 如何启用/禁用审计日志？

A: 在 `.env` 中配置：
```env
LOG_LEVEL=INFO  # INFO 以上级别启用审计
```
