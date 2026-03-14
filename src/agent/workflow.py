"""
LangGraph 工作流定义
基于 LLM 的智能体工作流
"""
import json
import re
from typing import Dict, List, Any, Optional, Callable
from langgraph.graph import StateGraph, END

from .state import AgentState, IntentType, ExtractedEntities, ToolParams
from .tools import execute_tool, AVAILABLE_TOOLS
from .time_context import get_time_context
from ..llm.client import get_llm
from ..utils.logger import logger


# ==================== 提示词模板 ====================

INTENT_PROMPT = """你是一个旅行助手意图识别专家。

用户问题: {user_query}

请分析用户想要做什么，只能选择以下一种意图:
- train_tickets: 查询火车票、高铁、动车
- weather: 查询天气、温度
- attractions: 查询景点、美食、网红打卡地
- transport: 交通方式查询
- hotel: 酒店住宿查询
- general: 其他问题

只输出JSON，不要其他内容:
{{"intent": "意图类型"}}
"""

ENTITY_PROMPT = """你是一个实体提取专家。

当前时间: {current_time}
用户问题: {user_query}

请从用户问题中提取以下实体，只输出JSON:

字段说明:
- origin: 出发地城市名（如"北京"、"上海"、"三明"）
- destination: 目的地城市名
- date_text: 用户提到的日期描述（如"明天"、"后天"、"下周一"）
- train_type: 火车类型（G高铁、D动车、K普快），如果没有则为空
- keyword: 搜索关键词（景点/美食/网红），如果没有则为空

重要规则:
1. "三明北站"是福建省三明市的火车站，出发地应填"三明"
2. 日期基于当前时间 {current_time} 计算
3. 只提取明确提到的信息，不要猜测

直接输出JSON:
{{"origin": "...", "destination": "...", "date_text": "...", "train_type": "...", "keyword": "..."}}
"""

DATE_PROMPT = """你是一个日期解析专家。

当前时间: {current_time}
用户给出的日期描述: {date_text}

请将日期描述转换为标准日期格式。

规则:
- "今天" = 当前时间
- "明天" = 当前时间 + 1天
- "后天" = 当前时间 + 2天
- "大后天" = 当前时间 + 3天
- "下周X" = 下周的周X
- "3月15日" = 当年的3月15日

直接输出JSON:
{{"parsed_date": "YYYY-MM-DD", "weekday": "星期X"}}
"""

TRAIN_PARAMS_PROMPT = """你是一个工具参数准备专家。

用户问题: {user_query}
提取的实体: {entities}

请为查询火车票准备正确的参数。

已知信息:
- 出发城市: {origin}
- 目的城市: {destination}
- 日期: {date}
- 火车类型: {train_type}

请输出JSON参数（注意站名格式）:
{{"from_station": "XXX站", "to_station": "XXX站", "date": "YYYY-MM-DD", "train_type": "G"}}

注意:
- 火车站名格式: 城市名+站，如"三明北站"、"宁波站"
- 如果不确定站名，可以使用通用名称如"{destination}站"
"""

WEATHER_PARAMS_PROMPT = """你是一个工具参数准备专家。

请为查询天气准备参数。

目的城市: {destination}

直接输出JSON:
{{"city": "城市名"}}
"""

ATTRACTION_PARAMS_PROMPT = """你是一个工具参数准备专家。

请为搜索景点准备参数。

目的城市: {destination}
搜索关键词: {keyword}

直接输出JSON:
{{"city": "城市名", "keyword": "关键词"}}
"""

RESPONSE_PROMPT = """你是友好的旅行助手。

用户问题: {user_query}
意图: {intent}
查询结果: {results}

请根据查询结果回答用户。要求:
1. 清晰说明查询到了什么信息
2. 如果查询失败，说明原因并给出建议
3. 使用emoji让回答更生动
4. 直接给出有用信息

回答:
"""


# ==================== 节点函数 ====================

def intent_recognition_node(state: AgentState) -> AgentState:
    """意图识别节点 - 使用 LLM"""
    user_query = state["user_query"]
    logger.info(f"[意图识别] {user_query[:30]}...")
    
    llm = get_llm()
    
    try:
        response = llm.chat(INTENT_PROMPT.format(user_query=user_query), user_query)
        
        # 解析 JSON
        intent_match = re.search(r'\{[\s\S]*\}', response)
        if intent_match:
            data = json.loads(intent_match.group())
            intent_str = data.get("intent", "general")
            
            # 转换为枚举
            try:
                intent = IntentType(intent_str)
            except:
                intent = IntentType.GENERAL
            
            state["intent"] = intent
            logger.info(f"[意图识别] 结果: {intent.value}")
        else:
            state["intent"] = IntentType.GENERAL
            
    except Exception as e:
        logger.error(f"[意图识别] 失败: {e}")
        state["intent"] = IntentType.GENERAL
    
    return state


def entity_extraction_node(state: AgentState) -> AgentState:
    """实体提取节点 - 使用 LLM"""
    user_query = state["user_query"]
    current_time = state["current_time"]
    logger.info(f"[实体提取] {user_query[:30]}...")
    
    llm = get_llm()
    
    try:
        response = llm.chat(
            ENTITY_PROMPT.format(current_time=current_time, user_query=user_query),
            user_query
        )
        
        # 解析 JSON
        entity_match = re.search(r'\{[\s\S]*\}', response)
        if entity_match:
            data = json.loads(entity_match.group())
            entities = ExtractedEntities(**data)
            state["entities"] = entities
            logger.info(f"[实体提取] 结果: {data}")
        else:
            state["entities"] = ExtractedEntities()
            
    except Exception as e:
        logger.error(f"[实体提取] 失败: {e}")
        state["entities"] = ExtractedEntities()
    
    return state


def date_parsing_node(state: AgentState) -> AgentState:
    """日期解析节点 - 使用 LLM"""
    entities = state.get("entities")
    current_time = state["current_time"]
    
    if not entities or not entities.date_text:
        # 没有日期，使用今天
        if entities:
            entities.parsed_date = current_time
        logger.info("[日期解析] 无日期，使用今天")
        return state
    
    date_text = entities.date_text
    logger.info(f"[日期解析] {date_text}")
    
    llm = get_llm()
    
    try:
        response = llm.chat(
            DATE_PROMPT.format(current_time=current_time, date_text=date_text),
            date_text
        )
        
        # 解析 JSON
        date_match = re.search(r'\{[\s\S]*\}', response)
        if date_match:
            data = json.loads(date_match.group())
            if entities:
                entities.parsed_date = data.get("parsed_date")
                entities.weekday = data.get("weekday")
            logger.info(f"[日期解析] 结果: {data}")
        
    except Exception as e:
        logger.error(f"[日期解析] 失败: {e}")
    
    return state


def prepare_params_node(state: AgentState) -> AgentState:
    """准备工具参数节点 - 使用 LLM"""
    intent = state.get("intent")
    entities = state.get("entities")
    user_query = state["user_query"]
    
    if not intent or not entities:
        state["tool_params"] = ToolParams()
        return state
    
    logger.info(f"[参数准备] 意图: {intent.value}")
    
    llm = get_llm()
    
    try:
        if intent == IntentType.TRAIN_TICKETS:
            # 火车票参数
            origin = entities.origin or ""
            destination = entities.destination or ""
            date = entities.parsed_date or ""
            train_type = entities.train_type or "G"
            
            response = llm.chat(
                TRAIN_PARAMS_PROMPT.format(
                    user_query=user_query,
                    entities=entities.model_dump_json(),
                    origin=origin,
                    destination=destination,
                    date=date,
                    train_type=train_type
                ),
                user_query
            )
            
            param_match = re.search(r'\{[\s\S]*\}', response)
            if param_match:
                data = json.loads(param_match.group())
                params = ToolParams(**data)
                state["tool_params"] = params
                logger.info(f"[参数准备] 火车票: {data}")
            
        elif intent == IntentType.WEATHER:
            # 天气参数
            destination = entities.destination or entities.origin or ""
            
            response = llm.chat(
                WEATHER_PARAMS_PROMPT.format(destination=destination),
                user_query
            )
            
            param_match = re.search(r'\{[\s\S]*\}', response)
            if param_match:
                data = json.loads(param_match.group())
                params = ToolParams(**data)
                state["tool_params"] = params
                logger.info(f"[参数准备] 天气: {data}")
            
        elif intent == IntentType.ATTRACTIONS:
            # 景点参数
            destination = entities.destination or ""
            keyword = entities.keyword or "景点"
            
            response = llm.chat(
                ATTRACTION_PARAMS_PROMPT.format(destination=destination, keyword=keyword),
                user_query
            )
            
            param_match = re.search(r'\{[\s\S]*\}', response)
            if param_match:
                data = json.loads(param_match.group())
                params = ToolParams(**data)
                state["tool_params"] = params
                logger.info(f"[参数准备] 景点: {data}")
        
        else:
            state["tool_params"] = ToolParams()
            
    except Exception as e:
        logger.error(f"[参数准备] 失败: {e}")
        state["tool_params"] = ToolParams()
    
    return state


def execute_tool_node(state: AgentState) -> AgentState:
    """工具执行节点"""
    intent = state.get("intent")
    params = state.get("tool_params")
    user_query = state["user_query"]
    
    if not intent or intent == IntentType.GENERAL:
        state["tool_results"] = {}
        state["success"] = True
        return state
    
    tool_name = _get_tool_name(intent)
    if not tool_name:
        state["tool_results"] = {}
        state["success"] = True
        return state
    
    # 准备参数
    tool_params = {}
    if intent == IntentType.TRAIN_TICKETS and params:
        tool_params = {
            "date": params.date or "",
            "from_station": params.from_station or "",
            "to_station": params.to_station or "",
            "train_type": params.train_type or "G"
        }
    elif intent == IntentType.WEATHER and params:
        tool_params = {"city": params.city or ""}
    elif intent == IntentType.ATTRACTIONS and params:
        tool_params = {"city": params.city or "", "keyword": params.keyword or "景点"}
    
    logger.info(f"[工具执行] {tool_name}: {tool_params}")
    
    # 执行工具
    try:
        result = execute_tool(tool_name, tool_params)
        
        # 解析结果
        try:
            result_data = json.loads(result)
        except:
            result_data = {"raw": result}
        
        state["tool_results"] = {tool_name: result_data}
        
        # 检查是否成功
        if "error" in result_data:
            state["success"] = False
            state["error_message"] = result_data.get("error")
            logger.warning(f"[工具执行] 失败: {result_data.get('error')}")
            
            # 执行降级
            fallback_result = _execute_fallback(state)
            if fallback_result:
                state["tool_results"][f"{tool_name}_fallback"] = fallback_result
                state["fallback_used"] = True
                state["success"] = True
        else:
            state["success"] = True
            logger.info(f"[工具执行] 成功")
            
    except Exception as e:
        logger.error(f"[工具执行] 异常: {e}")
        state["success"] = False
        state["error_message"] = str(e)
    
    return state


def _get_tool_name(intent: IntentType) -> Optional[str]:
    """获取意图对应的工具名"""
    mapping = {
        IntentType.TRAIN_TICKETS: "get_train_tickets",
        IntentType.WEATHER: "get_weather",
        IntentType.ATTRACTIONS: "search_attractions",
    }
    return mapping.get(intent)


def _execute_fallback(state: AgentState) -> Optional[Dict]:
    """执行降级搜索"""
    intent = state.get("intent")
    entities = state.get("entities")
    
    if not intent or not entities:
        return None
    
    logger.info(f"[降级] 执行降级搜索")
    
    try:
        if intent == IntentType.TRAIN_TICKETS:
            origin = entities.origin or ""
            destination = entities.destination or ""
            date = entities.parsed_date or ""
            
            query = f"{origin}到{destination}火车票 {date}"
            result = execute_tool("web_search", {"query": query})
            return {"web_search": json.loads(result) if "{" in result else {"raw": result}}
        
        elif intent == IntentType.WEATHER:
            city = entities.destination or entities.origin or ""
            result = execute_tool("web_search", {"query": f"{city}天气"})
            return {"web_search": json.loads(result) if "{" in result else {"raw": result}}
        
        elif intent == IntentType.ATTRACTIONS:
            city = entities.destination or ""
            keyword = entities.keyword or "景点"
            result = execute_tool("web_search", {"query": f"{city}{keyword}推荐"})
            return {"web_search": json.loads(result) if "{" in result else {"raw": result}}
    
    except Exception as e:
        logger.error(f"[降级] 失败: {e}")
    
    return None


def generate_response_node(state: AgentState) -> AgentState:
    """生成响应节点 - 使用 LLM"""
    user_query = state["user_query"]
    intent = state.get("intent")
    tool_results = state.get("tool_results", {})
    success = state.get("success", False)
    error_message = state.get("error_message")
    
    logger.info(f"[响应生成] 成功: {success}")
    
    # 构建结果描述
    results_text = ""
    for tool_name, result in tool_results.items():
        results_text += f"\n### {tool_name}\n"
        results_text += json.dumps(result, ensure_ascii=False, indent=2)
        results_text += "\n"
    
    if not results_text:
        results_text = "无查询结果"
    
    llm = get_llm()
    
    try:
        response = llm.chat(
            RESPONSE_PROMPT.format(
                user_query=user_query,
                intent=intent.value if intent else "unknown",
                results=results_text
            ),
            user_query
        )
        
        state["final_response"] = response
        
    except Exception as e:
        logger.error(f"[响应生成] 失败: {e}")
        
        if success:
            # 有结果但生成失败，尝试直接返回结果
            state["final_response"] = _format_simple_response(tool_results)
        else:
            state["final_response"] = f"抱歉，处理您的请求时出错: {error_message}"
    
    return state


def _format_simple_response(tool_results: Dict) -> str:
    """简单的响应格式化"""
    lines = []
    
    for tool_name, result in tool_results.items():
        if "error" in result:
            lines.append(f"查询失败: {result['error']}")
        else:
            lines.append(f"查询结果: {json.dumps(result, ensure_ascii=False)[:200]}")
    
    return "\n".join(lines) if lines else "暂无结果"


# ==================== 路由函数 ====================

def should_execute_tool(state: AgentState) -> str:
    """判断是否需要执行工具"""
    intent = state.get("intent")
    
    if not intent or intent == IntentType.GENERAL:
        return "direct_response"
    
    return "execute_tool"


def should_use_fallback(state: AgentState) -> str:
    """判断是否使用降级"""
    if state.get("fallback_used"):
        return "generate_response"
    
    return "execute_tool"


# ==================== 构建 LangGraph ====================

def create_agent_graph():
    """创建 Agent 工作流图"""
    
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("entity_extraction", entity_extraction_node)
    workflow.add_node("date_parsing", date_parsing_node)
    workflow.add_node("prepare_params", prepare_params_node)
    workflow.add_node("execute_tool", execute_tool_node)
    workflow.add_node("generate_response", generate_response_node)
    
    # 设置入口
    workflow.set_entry_point("intent_recognition")
    
    # 添加边
    workflow.add_edge("intent_recognition", "entity_extraction")
    workflow.add_edge("entity_extraction", "date_parsing")
    workflow.add_edge("date_parsing", "prepare_params")
    
    # 条件边：根据意图决定下一步
    workflow.add_conditional_edges(
        "prepare_params",
        should_execute_tool,
        {
            "execute_tool": "execute_tool",
            "direct_response": "generate_response"
        }
    )
    
    # 工具执行后的边
    workflow.add_edge("execute_tool", "generate_response")
    
    # 结束
    workflow.add_edge("generate_response", END)
    
    return workflow.compile()


# 全局图实例
_agent_graph = None


def get_agent_graph():
    """获取 Agent 图实例"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph


# ==================== 执行入口 ====================

def run_agent(user_query: str, session_id: str = None) -> Dict[str, Any]:
    """运行 Agent"""
    import uuid
    from datetime import datetime
    
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    
    # 获取当前时间
    time_ctx = get_time_context()
    current_time = time_ctx.get_today()
    
    # 初始化状态
    initial_state: AgentState = {
        "user_query": user_query,
        "session_id": session_id,
        "current_time": current_time,
        "intent": None,
        "entities": None,
        "tool_params": None,
        "steps": [],
        "tool_results": {},
        "final_response": "",
        "success": False,
        "error_message": None,
        "fallback_used": False,
        "retry_count": 0
    }
    
    # 运行图
    graph = get_agent_graph()
    
    try:
        result = graph.invoke(initial_state)
        return {
            "success": result.get("success", False),
            "response": result.get("final_response", ""),
            "intent": result.get("intent"),
            "entities": result.get("entities"),
            "tool_results": result.get("tool_results", {}),
            "fallback_used": result.get("fallback_used", False)
        }
    except Exception as e:
        logger.error(f"Agent 运行失败: {e}")
        return {
            "success": False,
            "response": f"处理失败: {str(e)}",
            "error": str(e)
        }