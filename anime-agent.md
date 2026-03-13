# 番剧信息获取智能体 - Agent 实现文档

## 项目概要

| 项目 | 说明 |
|------|------|
| **项目名称** | 番剧智能助手 (Anime Agent) |
| **核心框架** | ReAct 模式 + LangChain Tools |
| **LLM 提供商** | MiniMax (通过阿里云 DashScope) |
| **数据源** | Jikan API + AniList API + 百度搜索 (Fallback) |
| **部署方式** | FastAPI + SSE 流式输出 |

### 功能特性

- ✅ 支持关键词搜索番剧
- ✅ 支持时间范围查询 (如 "2024年7月")
- ✅ 多数据源并行查询
- ✅ 自动 fallback 到百度搜索
- ✅ 流式输出实时响应

---

## 一、项目背景与现状

### 1.1 测试结果回顾

| 测试项 | 结果 | 说明 |
|--------|------|------|
| MiniMax API 可用性 | ✅ 通过 | DashScope 兼容模式正常工作 |
| JSON 参数提取 | ✅ 通过 | 需要回退解析机制 |
| 文本格式化 | ✅ 通过 | 友好自然语言输出 |
| 流式输出 | ✅ 通过 | 支持实时对话 |
| 响应时间 | ⚠️ 警告 | 平均 5.8s，最长 68s |
| 批量稳定性 | ✅ 通过 | 3/3 成功率 |

### 1.2 核心问题识别

1. **响应时间过长**：测试5中响应时间达 68 秒，这是主要瓶颈
2. **双重 LLM 调用**：每次查询需要调用两次 MiniMax（意图解析 + 格式化），增加延迟
3. **缓存缺失**：相同查询重复调用 LLM，浪费资源
4. **数据源未集成**：当前使用模拟数据，需对接真实 API

---

## 二、Agent 架构设计（优化版）

### 2.1 整体架构

```

┌─────────────────────────────────────────────────────────────────┐

│                        用户请求入口                               │

│              (CLI / API / WebSocket 流式响应)                    │

└────────────────────────────┬────────────────────────────────────┘

                             │

┌────────────────────────────▼────────────────────────────────────┐

│                     Agent 编排层 (ReAct 模式)                     │

│  ┌────────────────────────────────────────────────────────────┐ │

│  │                    ReAct Agent                              │ │

│  │  - 意图分析 → 工具选择 → 执行 → 评估 → 重试                 │ │

│  │  - 支持多轮迭代，最大 5 次                                   │ │

│  │  - 自主决策重试策略                                          │ │

│  └────────────────────────────────────────────────────────────┘ │

└────────────────────────────┬────────────────────────────────────┘

                             │

┌────────────────────────────▼────────────────────────────────────┐

│                        LangChain Tools 层                        │

│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐

│  │ query_anime  │  │get_anime_   │  │get_anime_    │  │ web_search  │

│  │              │  │  detail     │  │  ranking     │  │  (百度搜索)  │

│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘

└────────────────────────────┬────────────────────────────────────┘

                             │

┌────────────────────────────▼────────────────────────────────────┐

│                        Skills 层                                │

│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │

│  │ AnimeQuery   │  │ AnimeDetail  │  │   Ranking   │         │

│  │   Skill     │  │   Skill      │  │   Skill     │         │

│  └──────────────┘  └──────────────┘  └──────────────┘         │

└────────────────────────────┬────────────────────────────────────┘

                             │

┌────────────────────────────▼────────────────────────────────────┐

│                    数据源适配器层                                │

│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │

│  │  Jikan API  │  │  AniList API │  │Baidu Search │        │

│  │(MyAnimeList)│  │  (全球数据)  │  │  (Fallback)  │        │

│  └──────────────┘  └──────────────┘  └──────────────┘        │

│                                                                  │

│  ┌──────────────┐  ┌──────────────┐                           │

│  │ DataSource   │  │  QueryCache  │                           │

│  │   Router     │  │              │                           │

│  └──────────────┘  └──────────────┘                           │

└─────────────────────────────────────────────────────────────────┘

```

### 2.2 优化策略

#### 2.2.1 单次 LLM 调用优化

**原方案问题**：每次查询调用两次 MiniMax
- 第一次：意图解析（提取查询参数）
- 第二次：格式化输出

**优化方案**：使用单次调用 + 结构化输出

```python
# 优化后的 prompt 设计
OPTIMIZED_PROMPT = """你是一个智能番剧助手。请根据用户查询一步完成：

1. 解析查询意图（时间、平台、类型、排序）
2. 如果已有数据，直接格式化输出；如果需要查询，说明需要的参数

用户查询：{query}

历史上下文：{context}

请以以下 JSON 格式输出：
{{
  "intent": {{
    "action": "query|detail|rank|suggest",  // 操作类型
    "time_range": "时间范围", 
    "platform": "平台",
    "anime_type": "类型",
    "sort_by": "排序方式",
    "keyword": "关键词"
  }},
  "response": "格式化回复（如果可以直接回答）",
  "needs_fetch": true/false  // 是否需要调用数据源
}}
"""
```

#### 2.2.2 缓存机制

```python
from functools import lru_cache
import hashlib
import json
import time

class QueryCache:
    """查询结果缓存"""
    
    def __init__(self, ttl: int = 3600):  # 默认 1 小时
        self._cache = {}
        self._ttl = ttl
    
    def _make_key(self, query: str, params: dict) -> str:
        """生成缓存 key"""
        data = json.dumps({"query": query, "params": params}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, query: str, params: dict) -> str | None:
        """获取缓存"""
        key = self._make_key(query, params)
        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return result
            else:
                del self._cache[key]
        return None
    
    def set(self, query: str, params: dict, value: str):
        """设置缓存"""
        key = self._make_key(query, params)
        self._cache[key] = (value, time.time())
```

#### 2.2.3 并行数据源请求

```python
import asyncio
import aiohttp

class DataSourceRouter:
    """数据源路由器"""
    
    def __init__(self, sources: list[AnimeDataSource]):
        self.sources = sources
    
    async def search(self, params: QueryParams) -> list[AnimeInfo]:
        """并行查询所有数据源"""
        
        async def fetch_with_timeout(source, timeout=5):
            try:
                return await asyncio.wait_for(source.search(params), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"{source.name} 查询超时")
                return []
            except Exception as e:
                logger.error(f"{source.name} 查询失败: {e}")
                return []
        
        # 并行执行，带超时保护
        results = await asyncio.gather(
            *[fetch_with_timeout(s) for s in self.sources],
            return_exceptions=True
        )
        
        # 合并结果并去重
        return self._merge_results([r for r in results if isinstance(r, list)])
    
    def _merge_results(self, results: list[list[AnimeInfo]]) -> list[AnimeInfo]:
        """合并去重"""
        seen = set()
        merged = []
        for result_list in results:
            for anime in result_list:
                if anime.id not in seen:
                    seen.add(anime.id)
                    merged.append(anime)
        return sorted(merged, key=lambda x: x.rating or 0, reverse=True)
```

---

## 三、Agent 核心实现

### 3.1 项目结构

```
anime-agent/
├── .env                          # 环境变量配置
├── .env.example                  # 环境变量示例
├── requirements.txt              # Python 依赖
├── agent.md                      # 项目文档
├── minimax使用手册.md            # MiniMax 使用手册
├── quickstart.md                 # 快速开始
├── src/
│   ├── __init__.py
│   ├── main.py                   # FastAPI 入口
│   ├── config.py                 # 配置管理
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py              # ReAct Agent 核心实现
│   │   └── tools.py             # LangChain Tools 定义
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py              # Skill 基类
│   │   ├── query.py             # 查询 Skill
│   │   ├── detail.py            # 详情 Skill
│   │   └── ranking.py           # 排行榜 Skill
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py            # MiniMax 客户端
│   │   └── prompts.py           # Prompt 模板
│   ├── data_sources/
│   │   ├── __init__.py
│   │   ├── base.py              # 数据源接口
│   │   ├── router.py            # 数据源路由器
│   │   ├── jikan.py            # Jikan API (MyAnimeList)
│   │   ├── anilist.py          # AniList API
│   │   ├── baidu_search.py     # 百度搜索 API
│   │   └── bangumi.py          # Bangumi API (备用)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── query_params.py
│   │   ├── anime_info.py
│   │   └── context.py
│   └── utils/
│       ├── __init__.py
│       ├── cache.py             # 缓存工具
│       └── logger.py            # 日志工具
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── tests/
```

### 3.2 Agent 状态定义

```python
# src/agent/state.py
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class AgentState(TypedDict):
    """Agent 状态定义"""
    # 输入
    messages: Annotated[list, add_messages]  # 消息历史
    user_query: str                          # 用户查询
    
    # 意图解析结果
    intent: dict | None                      # 解析后的意图
    query_params: dict | None                 # 查询参数
    
    # 数据源结果
    anime_results: list[dict] | None         # 番剧数据
    raw_response: str | None                  # LLM 原始响应
    
    # 输出
    final_response: str | None                # 最终回复
    error: str | None                         # 错误信息
    
    # 元数据
    needs_data_fetch: bool                    # 是否需要获取数据
    cache_hit: bool                           # 是否命中缓存
```

### 3.3 LangGraph 节点实现

```python
# src/agent/nodes.py
from langchain_core.messages import HumanMessage, AIMessage
from .state import AgentState
from ..llm.client import MiniMaxClient
from ..skills.query import AnimeQuerySkill
from ..utils.cache import QueryCache

# 全局缓存实例
query_cache = QueryCache(ttl=3600)

def parse_intent(state: AgentState) -> AgentState:
    """节点1：解析用户意图"""
    
    user_query = state["user_query"]
    messages = state.get("messages", [])
    
    # 检查缓存
    cached = query_cache.get(user_query, {})
    if cached:
        return {
            **state,
            "final_response": cached,
            "cache_hit": True
        }
    
    # 调用 LLM 解析意图
    client = MiniMaxClient()
    intent = client.parse_intent(user_query, messages)
    
    return {
        **state,
        "intent": intent.get("intent"),
        "query_params": intent.get("params"),
        "needs_data_fetch": intent.get("needs_fetch", True)
    }

def execute_skill(state: AgentState) -> AgentState:
    """节点2：执行 Skill 获取数据"""
    
    if state.get("cache_hit"):
        return state
    
    if not state.get("needs_data_fetch"):
        # LLM 已直接回答
        return {
            **state,
            "final_response": state["intent"].get("response")
        }
    
    # 调用数据源
    query_skill = AnimeQuerySkill()
    params = state.get("query_params", {})
    results = query_skill.execute(params)
    
    return {
        **state,
        "anime_results": results
    }

def format_response(state: AgentState) -> AgentState:
    """节点3：格式化响应"""
    
    if state.get("cache_hit") or state.get("final_response"):
        return state
    
    client = MiniMaxClient()
    anime_results = state.get("anime_results", [])
    user_query = state["user_query"]
    
    # 调用 LLM 格式化输出
    response = client.format_response(user_query, anime_results)
    
    # 缓存结果
    query_cache.set(user_query, {}, response)
    
    return {
        **state,
        "final_response": response
    }
```

### 3.4 LangGraph 流程定义

```python
# src/agent/graph.py
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import parse_intent, execute_skill, format_response

def create_agent_graph() -> StateGraph:
    """创建 Agent 流程图"""
    
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("execute_skill", execute_skill)
    graph.add_node("format_response", format_response)
    
    # 定义流程
    graph.add_edge(START, "parse_intent")
    
    # 条件分支：根据是否需要获取数据
    graph.add_conditional_edges(
        "parse_intent",
        lambda state: "skip_fetch" if not state.get("needs_data_fetch", True) else "fetch_data",
        {
            "skip_fetch": "format_response",
            "fetch_data": "execute_skill"
        }
    )
    
    graph.add_edge("execute_skill", "format_response")
    graph.add_edge("format_response", END)
    
    return graph.compile()

# 全局 Agent 实例
agent = create_agent_graph()
```

---

## 四、Skill 实现

### 4.1 Skill 基类

```python
# src/skills/base.py
from abc import ABC, abstractmethod
from typing import TypedDict

class SkillInput(TypedDict):
    """Skill 输入"""
    query_params: dict
    context: dict

class SkillOutput(TypedDict):
    """Skill 输出"""
    success: bool
    data: list[dict] | dict | None
    error: str | None
    metadata: dict

class BaseSkill(ABC):
    """Skill 基类"""
    
    name: str = "base_skill"
    description: str = "基础技能"
    
    @abstractmethod
    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """执行 Skill"""
        pass
    
    def can_handle(self, intent: dict) -> bool:
        """判断是否能处理该意图"""
        return intent.get("action") == self.name
    
    def _create_error_output(self, error: str) -> SkillOutput:
        """创建错误输出"""
        return {
            "success": False,
            "data": None,
            "error": error,
            "metadata": {"skill": self.name}
        }
```

### 4.2 番剧查询 Skill

```python
# src/skills/query.py
from .base import BaseSkill, SkillInput, SkillOutput
from ..data_sources.bangumi import BangumiAPI
from ..data_sources.bilibili import BilibiliAPI

class AnimeQuerySkill(BaseSkill):
    """番剧查询 Skill"""
    
    name = "query"
    description = "查询番剧列表"
    
    def __init__(self):
        self.data_sources = [
            BangumiAPI(),
            BilibiliAPI()
        ]
    
    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """执行查询"""
        try:
            params = input_data["query_params"]
            
            # 并行查询数据源
            from ..data_sources.router import DataSourceRouter
            router = DataSourceRouter(self.data_sources)
            
            # 构建 QueryParams
            from ..models.query_params import QueryParams
            query_params = QueryParams(
                time_range=params.get("time_range"),
                platform=params.get("platform", "all"),
                anime_type=params.get("anime_type", "all"),
                sort_by=params.get("sort_by", "latest"),
                keyword=params.get("keyword")
            )
            
            results = await router.search(query_params)
            
            # 转换为字典
            data = [anime.to_dict() for anime in results]
            
            return {
                "success": True,
                "data": data,
                "error": None,
                "metadata": {
                    "skill": self.name,
                    "count": len(data),
                    "sources": [s.name for s in self.data_sources]
                }
            }
            
        except Exception as e:
            return self._create_error_output(str(e))
```

---

## 五、MiniMax 客户端

### 5.1 客户端封装

```python
# src/llm/client.py
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration
from .prompts import INTENT_PROMPT, FORMAT_PROMPT

class MiniMaxClient:
    """MiniMax 模型客户端"""
    
    def __init__(self):
        self.client = ChatOpenAI(
            model=os.getenv("ORCH_MODEL", "MiniMax/MiniMax-M2.5"),
            temperature=0.1,  # 默认低温度
            max_tokens=2000,
            base_url=os.getenv("ORCH_API_BASE"),
            api_key=os.getenv("ORCH_API_KEY")
        )
        
        # 意图解析专用客户端（更低温度）
        self.intent_client = ChatOpenAI(
            model=os.getenv("ORCH_MODEL"),
            temperature=0.1,
            max_tokens=500,
            base_url=os.getenv("ORCH_API_BASE"),
            api_key=os.getenv("ORCH_API_KEY")
        )
    
    def parse_intent(self, query: str, context: list = None) -> dict:
        """解析用户意图"""
        
        context_str = ""
        if context:
            # 取最近3轮对话
            recent = context[-6:]  # 每轮2条消息
            context_str = "\n".join([
                f"{'用户' if i % 2 == 0 else '助手'}: {msg}"
                for i, msg in enumerate(recent)
            ])
        
        messages = [
            SystemMessage(content=INTENT_PROMPT),
            HumanMessage(content=f"用户查询：{query}\n\n历史上下文：{context_str}")
        ]
        
        response = self.intent_client.invoke(messages)
        
        # 解析 JSON 响应
        return self._parse_json_response(response.content)
    
    def format_response(self, query: str, anime_data: list) -> str:
        """格式化番剧数据"""
        
        messages = [
            SystemMessage(content=FORMAT_PROMPT),
            HumanMessage(content=f"用户查询：{query}\n\n番剧数据：{json.dumps(anime_data, ensure_ascii=False)}")
        ]
        
        response = self.client.invoke(messages)
        
        return response.content
    
    def _parse_json_response(self, content: str) -> dict:
        """解析 JSON 响应，包含回退机制"""
        
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 回退：尝试提取 JSON 块
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 最终回退：返回原始内容
        return {"raw": content, "error": "JSON解析失败"}
```

### 5.2 Prompt 模板

```python
# src/llm/prompts.py

INTENT_PROMPT = """你是一个智能番剧助手，负责解析用户的查询意图。

## 你的任务
1. 解析用户的查询意图
2. 提取查询参数
3. 判断是否需要调用数据源

## 输出格式
请严格按照以下 JSON 格式输出，不要输出其他内容：

{
  "intent": {
    "action": "query|detail|rank|suggest",
    "time_range": "时间范围（如2026-03、本周、最新）",
    "platform": "平台（bilibili/iqiyi/tencent/all）",
    "anime_type": "类型（日漫/国漫/美漫/剧场版/all）",
    "sort_by": "排序（latest/hot/rating）",
    "keyword": "关键词"
  },
  "needs_fetch": true或false,
  "response": "如果可以直接回答，则填写回答内容"
}

## 注意事项
- time_range 为空表示不限制时间
- platform 为 all 表示不限制平台
- 如果用户只是打招呼或闲聊，action 为 "suggest"
- 如果用户询问特定番剧详情，action 为 "detail"
"""

FORMAT_PROMPT = """你是专业的番剧推荐助手。请将番剧数据整理为友好的中文回复。

## 格式要求
1. 开头简短总结（如"找到 X 部番剧"）
2. 每部番剧包含：
   - 名称
   - 播出时间
   - 平台
   - 评分（如有）
   - 简介（30字内）
3. 末尾提供操作建议
4. 语言要自然流畅，符合中文表达习惯
5. 如果没有数据，回复"抱歉，暂无找到符合条件的番剧""

## 数据可能来自多个源，评分取最高值
"""
```

---

## 六、数据源适配器

### 6.1 数据源架构

当前项目使用多数据源架构，支持智能路由和 fallback：

```
┌─────────────────────────────────────────────────────────────┐
│                   DataSourceRouter (路由器)                   │
│  platform 参数映射：                                          │
│  - "jikan"   → Jikan API                                   │
│  - "anilist"  → AniList API                                 │
│  - "bangumi"  → Bangumi API                                 │
│  - "all"      → Jikan + AniList (默认)                      │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Jikan API (MyAnimeList)

```python
# src/data_sources/jikan.py
"""Jikan API - 免费的 MyAnimeList API"""

import aiohttp
from .base import AnimeDataSource
from ..models.anime_info import AnimeInfo
from ..models.query_params import QueryParams

class JikanAPI(AnimeDataSource):
    """Jikan API 数据源 - 基于 MyAnimeList"""
    
    BASE_URL = "https://api.jikan.moe/v4"
    NAME = "Jikan"
    
    # 季节映射
    SEASON_MAP = {
        "01": "winter", "02": "winter",
        "03": "spring", "04": "spring", "05": "spring",
        "06": "summer", "07": "summer", "08": "summer",
        "09": "fall", "10": "fall", "11": "fall",
        "12": "winter"
    }
    
    async def search(self, params: QueryParams) -> list[AnimeInfo]:
        # 关键词搜索
        if params.keyword:
            return await self._search_by_keyword(params)
        # 时间范围搜索
        if params.time_range:
            return await self._get_season(params)
        # 默认当前季度
        return await self._get_current_season(params)
```

### 6.3 AniList API (GraphQL)

```python
# src/data_sources/anilist.py
"""AniList API - GraphQL 格式"""

class AniListAPI(AnimeDataSource):
    """AniList API 数据源"""
    
    BASE_URL = "https://graphql.anilist.co"
    NAME = "AniList"
    
    async def search(self, params: QueryParams) -> list[AnimeInfo]:
        # 使用 GraphQL 查询
        query = """
        query ($season: MediaSeason, $year: Int, $sort: [MediaSort]) {
            Page(perPage: 20) {
                media(season: $season, seasonYear: $year, type: ANIME, sort: $sort) {
                    id
                    title { english romaji native }
                    averageScore
                    ...
                }
            }
        }
        """
```

### 6.4 百度搜索 API (Fallback)

```python
# src/data_sources/baidu_search.py
"""百度搜索 API - 最后的 fallback"""

class BaiduSearchAPI(AnimeDataSource):
    """百度搜索 API 数据源"""
    
    BASE_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    NAME = "BaiduSearch"
    
    async def search(self, params: QueryParams) -> list[AnimeInfo]:
        # 当其他数据源失败时使用
        # 调用百度千帆搜索 API
```

### 6.5 数据源路由

```python
# src/data_sources/router.py
class DataSourceRouter:
    """数据源路由器"""
    
    PLATFORM_MAP = {
        "jikan": ["Jikan"],
        "anilist": ["AniList"],
        "bangumi": ["Bangumi"],
        "all": ["Jikan", "AniList"],  # 默认
    }
    
    async def search(self, params: QueryParams) -> list[AnimeInfo]:
        # 并行查询多个数据源
        # 合并结果并按评分排序
```
                    f"{self.BASE_URL}/subjects/{bgm_id}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        return None
                    
                    raw = await resp.json()
                    return self._parse_anime(raw)
                    
        except Exception as e:
            logger.warning(f"Bangumi 详情查询失败: {e}")
            return None
```

### 6.2 数据源基类

```python
# src/data_sources/base.py
from abc import ABC, abstractmethod
from ..models.anime_info import AnimeInfo
from ..models.query_params import QueryParams

class AnimeDataSource(ABC):
    """番剧数据源抽象接口"""
    
    NAME = "base"
    
    @abstractmethod
    async def search(self, params: QueryParams) -> list[AnimeInfo]:
        """搜索番剧"""
        pass
    
    @abstractmethod
    async def get_detail(self, anime_id: str) -> AnimeInfo | None:
        """获取番剧详情"""
        pass
```

---

## 七、数据模型

### 7.1 QueryParams

```python
# src/models/query_params.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class QueryParams:
    """查询参数"""
    
    time_range: Optional[str] = None   # "2026-03", "本周", "最新"
    platform: str = "all"              # bilibili/iqiyi/tencent/all
    anime_type: str = "all"            # 日漫/国漫/美漫/剧场版/all
    sort_by: str = "latest"            # latest/hot/rating
    keyword: Optional[str] = None        # 搜索关键词
    
    def to_dict(self) -> dict:
        return {
            "time_range": self.time_range,
            "platform": self.platform,
            "anime_type": self.anime_type,
            "sort_by": self.sort_by,
            "keyword": self.keyword
        }
```

### 7.2 AnimeInfo

```python
# src/models/anime_info.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class AnimeInfo:
    """番剧信息"""
    
    id: str
    name: str
    name_cn: Optional[str]
    air_date: Optional[str]
    rating: Optional[float]
    summary: str
    platform: str
    source_url: str
    cover_url: Optional[str] = None
    tags: list[str] = None
    
    @property
    def display_name(self) -> str:
        """显示名称"""
        return self.name_cn or self.name
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "名称": self.display_name,
            "原名": self.name,
            "播出时间": self.air_date,
            "评分": self.rating,
            "简介": self.summary[:50] + "..." if len(self.summary) > 50 else self.summary,
            "平台": self.platform,
            "链接": self.source_url,
            "封面": self.cover_url
        }
```

---

## 八、环境配置与安装

> ⚠️ **重要提示**：本项目使用 conda 环境，请先激活环境后再执行任何 Python 命令！
> 
> ```bash
> conda activate langgraph-env
> ```

### 8.1 环境要求

- Python 3.10+
- MiniMax API Key（通过阿里云 DashScope 获取）
- conda 或 venv 虚拟环境管理

### 8.2 依赖安装（推荐使用 conda）

```bash
# 方法一：使用 conda 创建新环境（推荐）
conda create -n anime-agent python=3.11 -y
conda activate anime-agent

# 方法二：使用 venv
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 8.3 安装项目依赖

```bash
# 方式一：直接安装（从 PyPI）
pip install -r requirements.txt

# 方式二：安装时使用国内镜像（推荐国内用户）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 方式三：开发模式安装
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 8.4 环境变量配置

```bash
# 创建 .env 文件
copy .env.example .env
```

编辑 `.env` 文件，配置以下内容：

```env
# MiniMax 配置（必需）
ORCH_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORCH_MODEL=MiniMax/MiniMax-M2.5
ORCH_API_KEY=sk-your-api-key-here

# 百度搜索 API 配置（可选，用于 fallback）
# 通过百度智能云千帆获取：https://qianfan.baidubce.com/
BAIDU_SEARCH_API_KEY=your-baidu-api-key-here

# 日志配置（可选）
LOG_LEVEL=INFO

# 缓存配置（可选）
CACHE_TTL=3600
```

### 8.5 验证安装

```bash
# 运行测试验证环境
python test_minimax.py

# 或使用 pytest
pytest tests/ -v
```

### 8.6 依赖说明

| 依赖包 | 用途 | 必需 |
|--------|------|------|
| langchain-openai | MiniMax API 调用 | ✅ |
| langgraph | Agent 流程编排 | ✅ |
| aiohttp | 异步 HTTP 请求 | ✅ |
| pydantic | 数据验证 | ✅ |
| fastapi | Web 服务框架 | ✅ |
| uvicorn | ASGI 服务器 | ✅ |
| python-dotenv | 环境变量管理 | ✅ |
| loguru | 日志记录 | ✅ |
| pytest | 单元测试 | ✅ |

---

## 九、快速启动

### 8.1 环境配置

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env，填入 API Key
```

### 8.2 .env 示例

```env
# MiniMax 配置
ORCH_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORCH_MODEL=MiniMax/MiniMax-M2.5
ORCH_API_KEY=sk-xxxxxxxxxxxxxxxx

# 日志
LOG_LEVEL=INFO

# 缓存配置
CACHE_TTL=3600
```

### 8.3 运行测试

```bash
# 运行单元测试
pytest tests/ -v

# 启动服务
uvicorn src.main:app --reload

# 访问 API 文档
# http://localhost:8000/docs
```

### 8.4 API 调用示例

```python
# 直接使用 Agent
from src.agent.graph import agent

result = agent.invoke({
    "messages": [],
    "user_query": "2026年3月最新的日漫番剧有哪些？"
})

print(result["final_response"])
```

---

## 十、LangChain Tools 设计

### 10.1 Tools 架构概述

将 Skills 封装为 LangChain Tools，使 LLM 能够自动调用工具函数：

```
┌─────────────────────────────────────────────────────────────┐
│                      ReAct Agent                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  LLM (MiniMax) + Tools                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │  │
│  │  │query_anime │ │get_detail  │ │get_ranking │   │  │
│  │  │  Tool      │ │   Tool     │ │   Tool     │   │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │ web_search Tool (百度搜索 - Fallback)        │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │    MiniMax LLM             │
              │    (自动决定调用哪个工具)   │
              │    - 支持多轮迭代          │
              │    - 自主决策重试策略      │
              └────────────────────────────┘
```

### 10.2 当前 Tools 定义

```python
# src/agent/tools.py
"""LangChain Tools 定义"""

from langchain_core.tools import BaseTool
from pydantic import Field
from ..skills.query import AnimeQuerySkill
from ..skills.detail import AnimeDetailSkill
from ..skills.ranking import RankingSkill


class QueryAnimeInput(BaseTool):
    """query_anime 工具的参数"""
    time_range: str = Field(default="", description="时间范围，如 '2026-02'、'2024年7月'、'本月'、'最新'")
    platform: str = Field(default="all", description="平台：'jikan'、'anilist'、'bangumi'、'all'")
    anime_type: str = Field(default="all", description="类型：'日漫'、'国漫'、'all'")
    sort_by: str = Field(default="rating", description="排序：'latest'、'hot'、'rating'")
    keyword: str = Field(default="", description="关键词搜索，如番剧名称")


class QueryAnimeTool(BaseTool):
    """番剧查询工具 - 最重要！"""
    
    name: str = "query_anime"
    description: str = """查询番剧列表。
    
**重要**：当用户询问特定番剧时（如"《xxx》讲了什么"），必须使用 keyword 参数！

参数：
- time_range: 时间范围
- platform: 平台选择（jikan/anilist/bangumi/all）
- keyword: 关键词搜索（最重要！）"""


class WebSearchTool(BaseTool):
    """网页搜索工具 - Fallback"""
    
    name: str = "web_search"
    description: str = """通用网页搜索工具。

当数据库查询失败时使用此工具搜索互联网。
- query: 搜索关键词
- 这是最后的 fallback 手段！"""


def create_tools() -> list[BaseTool]:
    """创建所有 LangChain Tools"""
    return [
        QueryAnimeTool(),
        GetAnimeDetailTool(),
        GetAnimeRankingTool(),
        WebSearchTool()  # 新增百度搜索
    ]
```


def _run_sync(skill, params: dict) -> str:
    """同步执行 Skill"""
    import asyncio
    try:
        result = asyncio.run(skill.execute({
            "query_params": params,
            "context": {}
        }))
        
        if result.get("success"):
            import json
            return json.dumps(result.get("data", []), ensure_ascii=False, indent=2)
        else:
            return f"查询失败: {result.get('error')}"
    except Exception as e:
        return f"执行错误: {str(e)}"
```

### 10.3 Agent + Tools 使用

```python
# src/agent/langchain_agent.py
"""LangChain Agent with Tools"""

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from .tools import create_tools


def create_langchain_agent() -> AgentExecutor:
    """创建 LangChain Agent"""
    
    # 创建 LLM
    llm = ChatOpenAI(
        model="MiniMax/MiniMax-M2.5",
        temperature=0.7,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="your-api-key"
    )
    
    # 创建 Tools
    tools = create_tools()
    
    # 创建 Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业的番剧推荐助手。你可以调用工具来查询番剧信息。

        可用的工具：
        - query_anime: 查询番剧列表
        - get_anime_detail: 获取番剧详情
        - get_anime_ranking: 获取排行榜

        请根据用户的问题，选择合适的工具来回答。如果用户只是打招呼，直接回复即可。"""),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    # 创建 Agent
    agent = create_openai_functions_agent(llm, tools, prompt)
    
    # 创建 Executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5
    )
    
    return executor


# 使用示例
if __name__ == "__main__":
    executor = create_langchain_agent()
    
    # 简单查询
    result = executor.invoke({
        "input": "2026年3月有什么好看的日漫？"
    })
    print(result["output"])
    
    # 排行榜查询
    result = executor.invoke({
        "input": "给我推荐评分最高的番剧TOP10"
    })
    print(result["output"])
```

---

## 十一、前端界面设计

### 11.1 界面概述

Web 端交互界面，提供：
- 智能对话窗口
- 快捷操作按钮
- 流式响应展示
- 番剧结果展示

### 11.2 界面预览

```
┌─────────────────────────────────────────────────────────────┐
│  🎬 番剧智能助手                              [API 状态: ✓]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    对话区域                           │    │
│  │                                                     │    │
│  │  🤖 你好！我是番剧智能助手                          │    │
│  │     有什么番剧想了解的吗？                          │    │
│  │                                                     │    │
│  │                              用户  刚才           │    │
│  │  ┌─────────────────────────────────────────────┐   │    │
│  │  │ 2026年3月最新番剧有哪些？                    │   │    │
│  │  └─────────────────────────────────────────────┘   │    │
│  │                                                     │    │
│  │  🤖 正在查询...                                    │    │
│  │                                                     │    │
│  │  ┌─────────────────────────────────────────────┐   │    │
│  │  │ 找到 5 部 2026 年 3月最新番剧：            │   │    │
│  │  │                                             │   │    │
│  │  │ 1. 葬送的芙莉莲 ★9.2                        │   │    │
│  │  │    播出: 2026-03-01 | 平台: Bilibili       │   │    │
│  │  │                                             │   │    │
│  │  │ 2. 间谍过家家 ★8.8                          │   │    │
│  │  │    播出: 2026-03-05 | 平台: Bilibili       │   │    │
│  │  └─────────────────────────────────────────────┘   │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  快捷操作                                           │    │
│  │  [🔍 最新番剧] [🔥 热门排行] [⭐ 评分最高]        │    │
│  │  [🎌 日漫] [🇨🇳 国漫] [🎬 剧场版]                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────┐ [发送]    │
│  │ 输入你想了解的番剧...                               │          │
│  └─────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 11.3 前端实现文件

#### 11.3.1 HTML 结构

```html
<!-- index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>番剧智能助手</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <h1>🎬 番剧智能助手</h1>
            <span class="status" id="apiStatus">API 状态: 检测中...</span>
        </header>
        
        <!-- 对话区域 -->
        <div class="chat-container">
            <div class="messages" id="messages">
                <div class="message bot">
                    <div class="avatar">🤖</div>
                    <div class="content">你好！我是番剧智能助手。有什么番剧想了解的吗？</div>
                </div>
            </div>
            
            <!-- 快捷操作 -->
            <div class="quick-actions">
                <button class="action-btn" data-query="2026年3月最新番剧有哪些？">
                    🔍 最新番剧
                </button>
                <button class="action-btn" data-query="有什么热门番剧推荐？">
                    🔥 热门排行
                </button>
                <button class="action-btn" data-query="评分最高的番剧有哪些？">
                    ⭐ 评分最高
                </button>
                <button class="action-btn" data-query="推荐好看的日漫">
                    🎌 日漫
                </button>
                <button class="action-btn" data-query="推荐国漫">
                    🇨🇳 国漫
                </button>
                <button class="action-btn" data-query="有什么剧场版推荐？">
                    🎬 剧场版
                </button>
            </div>
            
            <!-- 输入区域 -->
            <div class="input-area">
                <input type="text" id="userInput" placeholder="输入你想了解的番剧..." autocomplete="off">
                <button id="sendBtn">发送</button>
            </div>
        </div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

#### 11.3.2 CSS 样式

```css
/* styles.css */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
}

.container {
    width: 100%;
    max-width: 800px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    overflow: hidden;
}

.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    font-size: 20px;
    font-weight: 600;
}

.status {
    font-size: 12px;
    padding: 4px 12px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 12px;
}

.status.online {
    background: #4ade80;
    color: #166534;
}

.chat-container {
    display: flex;
    flex-direction: column;
    height: 600px;
}

.messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.message {
    display: flex;
    gap: 12px;
    max-width: 85%;
}

.message.user {
    align-self: flex-end;
    flex-direction: row-reverse;
}

.message.bot {
    align-self: flex-start;
}

.avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

.message.user .avatar {
    background: #667eea;
}

.message.bot .avatar {
    background: #f3f4f6;
}

.content {
    padding: 12px 16px;
    border-radius: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
}

.message.user .content {
    background: #667eea;
    color: white;
    border-bottom-right-radius: 4px;
}

.message.bot .content {
    background: #f3f4f6;
    color: #1f2937;
    border-bottom-left-radius: 4px;
}

.quick-actions {
    padding: 12px 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    border-top: 1px solid #e5e7eb;
    background: #f9fafb;
}

.action-btn {
    padding: 8px 16px;
    border: 1px solid #e5e7eb;
    border-radius: 20px;
    background: white;
    color: #4b5563;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
}

.action-btn:hover {
    background: #667eea;
    color: white;
    border-color: #667eea;
}

.input-area {
    padding: 16px 20px;
    display: flex;
    gap: 12px;
    border-top: 1px solid #e5e7eb;
    background: white;
}

.input-area input {
    flex: 1;
    padding: 12px 16px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
}

.input-area input:focus {
    border-color: #667eea;
}

.input-area button {
    padding: 12px 24px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
}

.input-area button:hover {
    background: #5a67d8;
}

.input-area button:disabled {
    background: #9ca3af;
    cursor: not-allowed;
}

/* 加载动画 */
.loading .content::after {
    content: '';
    animation: dots 1.5s infinite;
}

@keyframes dots {
    0%, 20% { content: '.'; }
    40% { content: '..'; }
    60%, 100% { content: '...'; }
}

/* 响应式 */
@media (max-width: 600px) {
    .container {
        border-radius: 0;
        height: 100vh;
    }
    
    .message {
        max-width: 95%;
    }
}
```

#### 11.3.3 JavaScript 交互

```javascript
// app.js
class AnimeChatbot {
    constructor() {
        this.messagesContainer = document.getElementById('messages');
        this.userInput = document.getElementById('userInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.apiStatus = document.getElementById('apiStatus');
        
        this.init();
    }
    
    init() {
        // 绑定事件
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
        
        // 绑定快捷操作
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                this.userInput.value = query;
                this.sendMessage();
            });
        });
        
        // 检查 API 状态
        this.checkApiStatus();
    }
    
    async checkApiStatus() {
        try {
            const response = await fetch('/health');
            if (response.ok) {
                this.apiStatus.textContent = 'API 状态: ✓ 在线';
                this.apiStatus.classList.add('online');
            }
        } catch (e) {
            this.apiStatus.textContent = 'API 状态: ✗ 离线';
        }
    }
    
    async sendMessage() {
        const message = this.userInput.value.trim();
        if (!message) return;
        
        // 添加用户消息
        this.addMessage(message, 'user');
        this.userInput.value = '';
        
        // 添加加载状态
        const loadingMsg = this.addMessage('正在查询...', 'bot', true);
        
        try {
            // 调用 API
            const response = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: message })
            });
            
            const data = await response.json();
            
            // 移除加载消息
            loadingMsg.remove();
            
            // 添加回复
            this.addMessage(data.response, 'bot');
            
        } catch (e) {
            loadingMsg.remove();
            this.addMessage('抱歉，出现了错误: ' + e.message, 'bot');
        }
    }
    
    addMessage(content, type, isLoading = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}${isLoading ? ' loading' : ''}`;
        
        const avatar = type === 'user' ? '👤' : '🤖';
        
        messageDiv.innerHTML = `
            <div class="avatar">${avatar}</div>
            <div class="content">${content}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        
        return messageDiv;
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    new AnimeChatbot();
});
```

### 11.4 启动方式

```bash
# 1. 启动后端 API 服务
uvicorn src.main:app --reload

# 2. 启动静态文件服务器
# 方式一：使用 Python 内置服务器
python -m http.server 8080 --directory frontend

# 方式二：使用 Node.js (如果安装了)
npx serve frontend

# 3. 访问 http://localhost:8080
```

---

## 十二、快速命令汇总

```bash
# 环境搭建
conda create -n anime-agent python=3.11 -y
conda activate anime-agent
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 启动服务
# 终端1: 启动后端
uvicorn src.main:app --reload

# 终端2: 启动前端
python -m http.server 8080 --directory frontend

# 访问
# 后端 API: http://localhost:8000/docs
# 前端页面: http://localhost:8080
```

---

**文档版本**: v2.2
**更新日期**: 2026-03-10
**更新内容**: 
- 添加 LangChain Tools 设计
- 添加前端界面设计
- 修复 asyncio 异步调用问题
- 添加模拟数据支持测试

---

# 项目总结

## 核心功能

| 功能 | 说明 |
|------|------|
| 意图识别 | 自动解析用户查询意图（时间、平台、类型、排序） |
| 数据查询 | 从 Bangumi/Bilibili 获取番剧数据 |
| 智能回复 | MiniMax LLM 格式化输出 |
| 前端界面 | Web 聊天界面 + 快捷操作按钮 |

## 文件清单

```
anime-agent/
├── .env                    # 环境变量（API Key）
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── agent.md               # 完整技术文档
├── quickstart.md          # 快速启动指南
├── test_minimax.py        # API 测试脚本
├── src/                   # 后端源码
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # 配置管理
│   ├── agent/            # Agent 编排层
│   │   ├── graph.py     # LangGraph 定义
│   │   ├── nodes.py     # 节点实现
│   │   ├── state.py     # 状态定义
│   │   └── tools.py     # LangChain Tools
│   ├── skills/           # 技能模块
│   │   ├── base.py      # Skill 基类
│   │   ├── query.py     # 查询 Skill
│   │   ├── detail.py   # 详情 Skill
│   │   └── ranking.py   # 排行榜 Skill
│   ├── llm/             # LLM 客户端
│   │   ├── client.py   # MiniMax 封装
│   │   └── prompts.py  # Prompt 模板
│   ├── data_sources/    # 数据源
│   │   ├── base.py     # 数据源接口
│   │   ├── bangumi.py  # Bangumi 适配器
│   │   ├── bilibili.py # Bilibili 适配器
│   │   └── router.py   # 数据源路由
│   ├── models/          # 数据模型
│   └── utils/           # 工具类
├── frontend/            # 前端页面
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── tests/               # 测试代码
```

## 启动命令汇总

```bash
# 1. 激活环境
conda activate anime-agent

# 2. 启动后端（终端1）
uvicorn src.main:app --reload

# 3. 启动前端（终端2）
cd frontend
python -m http.server 8080

# 4. 访问
# 前端: http://localhost:8080
# API 文档: http://localhost:8000/docs
```
