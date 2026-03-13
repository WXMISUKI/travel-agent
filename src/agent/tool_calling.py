"""
LangChain Tool Calling Agent - 简化版
使用OpenAI原生Function Calling
"""
import json
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from .tools import AVAILABLE_TOOLS, get_all_tools, execute_tool
from ..config import ORCH_API_BASE, ORCH_MODEL, ORCH_API_KEY
from ..utils.logger import logger


# 系统提示词 - 强制要求提取参数
SYSTEM_PROMPT = """你是旅行规划助手，负责帮用户查询信息。

## 重要规则
1. 用户要查火车票时，必须先调用get_station_by_city把城市名转换为火车站名
2. 用户说"明天"、"后天"等日期时，必须先调用parse_date获取标准日期
3. 所有参数必须完整提供，不能省略

## 工具调用格式
如果需要调用工具，必须按以下JSON格式输出（不要有其他内容）：
{"name": "工具名", "arguments": {"参数1": "值1", "参数2": "值2"}}

例如：
{"name": "parse_date", "arguments": {"date_text": "明天"}}
{"name": "get_station_by_city", "arguments": {"city": "沙县"}}

## 工具列表
{tool_list}

现在开始处理用户请求："""


def get_tool_schemas():
    """获取简化的工具schema"""
    tools = []
    
    tool_defs = {
        "get_weather": {
            "description": "查询城市天气",
            "params": {"city": "城市名称，如杭州、上海"}
        },
        "get_train_tickets": {
            "description": "查询火车票，注意参数必须是火车站名不是城市名",
            "params": {
                "date": "日期格式YYYY-MM-DD",
                "from_station": "出发站（火车站名）",
                "to_station": "到达站（火车站名）",
                "train_type": "G高铁/D动车/K普快，默认G"
            }
        },
        "search_attractions": {
            "description": "搜索景点美食",
            "params": {"city": "城市名称", "keyword": "景点/美食/酒店"}
        },
        "web_search": {
            "description": "通用搜索",
            "params": {"query": "搜索内容"}
        },
        "get_current_date": {
            "description": "获取当前日期",
            "params": {}
        },
        "parse_date": {
            "description": "解析自然语言日期",
            "params": {"date_text": "明天/后天/下周一/3月15日等"}
        },
        "get_station_by_city": {
            "description": "查询城市附近的火车站",
            "params": {"city": "城市名称"}
        }
    }
    
    for name, defn in tool_defs.items():
        props = {}
        required = []
        for pname, desc in defn["params"].items():
            props[pname] = {"type": "string", "description": desc}
            required.append(pname)
        
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": defn["description"],
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required if required else []
                }
            }
        })
    
    return tools


class ToolCallingAgent:
    """使用OpenAI Function Calling的Agent"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=ORCH_MODEL,
            temperature=0.1,
            max_tokens=2000,
            base_url=ORCH_API_BASE,
            api_key=ORCH_API_KEY
        )
        
        self.tools = get_all_tools()
        self.tool_schemas = get_tool_schemas()
        self.llm_with_tools = self.llm.bind(tools=self.tool_schemas)
        
        logger.info(f"ToolCallingAgent初始化，工具数: {len(self.tools)}")
    
    def run(self, user_input: str, history: List[Dict] = None) -> Dict:
        """运行Agent"""
        try:
            # 构建工具列表文本
            tool_list_text = "\n".join([
                f"- {name}: {info['description']}"
                for name, info in AVAILABLE_TOOLS.items()
            ])
            
            # 准备消息 - 使用f-string避免格式化冲突
            system_msg = f"""你是旅行规划助手，负责帮用户查询信息。

## 重要规则
1. 用户要查火车票时，必须先调用get_station_by_city把城市名转换为火车站名
2. 用户说"明天"、"后天"等日期时，必须先调用parse_date获取标准日期
3. 所有参数必须完整提供，不能省略

## 工具调用格式
如果需要调用工具，必须按以下JSON格式输出（不要有其他内容）：
TOOL_CALL: {{"name": "工具名", "arguments": {{"参数1": "值1"}}}}

## 工具列表
{tool_list_text}

现在开始处理用户请求："""
            
            messages = [
                SystemMessage(content=system_msg)
            ]
            
            # 添加历史
            if history:
                for msg in history[-4:]:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg.get("content", "")))
            
            messages.append(HumanMessage(content=user_input))
            
            max_iterations = 8
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # 调用LLM
                response = self.llm_with_tools.invoke(messages)
                
                # 检查工具调用
                tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
                
                if not tool_calls:
                    # 没有工具调用，返回回复
                    return {
                        "success": True,
                        "output": response.content if hasattr(response, 'content') else str(response),
                        "steps": [],
                        "error": None
                    }
                
                # 执行工具调用
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("arguments", {})
                    
                    # 调试日志
                    logger.info(f"工具调用: {tool_name}, 参数: {tool_args}")
                    
                    # 如果arguments是字符串，解析它
                    if isinstance(tool_args, str):
                        try:
                            tool_args = json.loads(tool_args)
                        except:
                            logger.warning(f"无法解析参数: {tool_args}")
                            tool_args = {}
                    
                    # 执行工具
                    try:
                        result = execute_tool(tool_name, tool_args)
                        logger.info(f"工具结果: {result[:200]}...")
                    except Exception as e:
                        logger.error(f"工具执行失败: {e}")
                        result = json.dumps({"error": str(e)})
                    
                    # 添加消息
                    messages.append(AIMessage(content=""))
                    messages[-1].tool_calls = [tool_call]
                    messages.append(ToolMessage(content=result, tool_call_id=tool_call.get("id", "")))
            
            return {
                "success": True,
                "output": "处理完成",
                "steps": [],
                "error": "达到最大迭代"
            }
            
        except Exception as e:
            logger.error(f"Agent执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "output": f"出错: {str(e)}",
                "steps": [],
                "error": str(e)
            }


# 全局实例
_agent = None


def get_tool_calling_agent() -> ToolCallingAgent:
    global _agent
    if _agent is None:
        _agent = ToolCallingAgent()
    return _agent
