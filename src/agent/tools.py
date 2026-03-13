"""
LangChain Tools 定义 - 兼容MiniMax格式
"""
import json
import asyncio
from langchain_core.tools import BaseTool
from typing import Optional
from ..data_sources.weather import OpenMeteoAPI
from ..data_sources.mcp_client import MCPClient
from ..data_sources.baidu_search import BaiduSearchAPI
from ..utils.logger import logger


# 全局数据源实例
_weather_api = None
_mcp_client = None
_baidu_search = None


def get_weather_api() -> OpenMeteoAPI:
    global _weather_api
    if _weather_api is None:
        _weather_api = OpenMeteoAPI()
    return _weather_api


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


def get_baidu_search() -> BaiduSearchAPI:
    global _baidu_search
    if _baidu_search is None:
        _baidu_search = BaiduSearchAPI()
    return _baidu_search


def get_weather(city: str) -> str:
    """查询指定城市的天气预报
    
    参数:
        city: 城市名称，如'北京'、'上海'、'杭州'
    
    返回:
        城市的天气信息，包括当前天气和未来几天预报
    """
    try:
        api = get_weather_api()
        result = asyncio.run(api.get_weather(city))
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"天气查询失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_train_tickets(date: str, from_station: str, to_station: str, 
                      train_type: str = "G") -> str:
    """查询12306火车票余票信息
    
    参数:
        date: 出发日期，格式yyyy-MM-dd，如'2026-03-15'
        from_station: 出发城市或车站名，如'北京'、'上海'、'宁波'
        to_station: 到达城市或车站名，如'上海'、'杭州'、'南京'
        train_type: 车次类型筛选，G=高铁，D=动车，K=快速，T=特快，不填则查全部
    
    返回:
        火车票列表，包括车次、出发/到达时间、票价、余票等信息
    """
    try:
        client = get_mcp_client()
        result = client.get_tickets(date, from_station, to_station, train_type)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"车票查询失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def search_attractions(city: str, keyword: str = "景点") -> str:
    """搜索城市内的景点、美食、网红打卡地
    
    参数:
        city: 城市名称
        keyword: 搜索关键词，如'景点'、'美食'、'网红餐厅'、'必吃榜'
    
    返回:
        搜索结果列表
    """
    try:
        api = get_baidu_search()
        result = asyncio.run(api.search(city, keyword))
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"景点搜索失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_current_date() -> str:
    """获取当前日期
    
    返回:
        当前日期字符串，格式yyyy-MM-dd
    """
    try:
        client = get_mcp_client()
        date = client.get_current_date()
        return json.dumps({"current_date": date}, ensure_ascii=False)
    except Exception as e:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        return json.dumps({"current_date": date}, ensure_ascii=False)


# 工具定义 - 兼容MiniMax
AVAILABLE_TOOLS = {
    "get_weather": {
        "function": get_weather,
        "description": "查询指定城市的天气预报",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，如'北京'、'上海'、'杭州'"}
            },
            "required": ["city"]
        }
    },
    "get_train_tickets": {
        "function": get_train_tickets,
        "description": "查询12306火车票余票信息",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "出发日期，格式yyyy-MM-dd"},
                "from_station": {"type": "string", "description": "出发城市或车站名"},
                "to_station": {"type": "string", "description": "到达城市或车站名"},
                "train_type": {"type": "string", "description": "车次类型：G/D/K/T，不填则查全部"}
            },
            "required": ["date", "from_station", "to_station"]
        }
    },
    "search_attractions": {
        "function": search_attractions,
        "description": "搜索城市内的景点、美食、网红打卡地",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "keyword": {"type": "string", "description": "搜索关键词，如'景点'、'美食'"}
            },
            "required": ["city"]
        }
    },
    "get_current_date": {
        "function": get_current_date,
        "description": "获取当前日期",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}


def get_all_tools():
    """获取所有工具函数"""
    return [info["function"] for info in AVAILABLE_TOOLS.values()]


def get_tool_schemas():
    """获取工具schema定义"""
    schemas = []
    for name, info in AVAILABLE_TOOLS.items():
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"]
            }
        })
    return schemas


def execute_tool(tool_name: str, arguments: dict) -> str:
    """执行工具"""
    if tool_name in AVAILABLE_TOOLS:
        func = AVAILABLE_TOOLS[tool_name]["function"]
        try:
            # 根据参数数量调用
            import inspect
            sig = inspect.signature(func)
            if len(sig.parameters) == 0:
                return func()
            else:
                return func(**arguments)
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    else:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
