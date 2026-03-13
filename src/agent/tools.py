"""
LangChain Tools 定义 - 简化版
不使用@tool装饰器，直接使用普通函数
"""
import json
import asyncio
from typing import Optional
from ..data_sources.weather import OpenMeteoAPI
from ..data_sources.mcp_client import MCPClient
from ..data_sources.baidu_search import BaiduSearchAPI
from ..utils.logger import logger

# 解决asyncio嵌套问题
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass


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
    """查询指定城市的天气预报"""
    try:
        api = get_weather_api()
        try:
            result = asyncio.run(api.get_weather(city))
            return json.dumps(result, ensure_ascii=False, indent=2)
        except RuntimeError:
            result = asyncio.run(api.get_weather(city))
            return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"天气查询失败: {e}")
        return json.dumps({"error": str(e), "city": city}, ensure_ascii=False)


def get_train_tickets(date: str, from_station: str, to_station: str, train_type: str = "G") -> str:
    """查询12306火车票"""
    try:
        client = get_mcp_client()
        result = client.get_tickets(date, from_station, to_station, train_type)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"车票查询失败: {e}")
        return json.dumps({
            "error": str(e), 
            "from_station": from_station,
            "to_station": to_station
        }, ensure_ascii=False)


def search_attractions(city: str, keyword: str = "景点") -> str:
    """搜索城市内的景点、美食"""
    try:
        api = get_baidu_search()
        try:
            result = asyncio.run(api.search(city, keyword))
            return json.dumps(result, ensure_ascii=False, indent=2)
        except RuntimeError:
            result = asyncio.run(api.search(city, keyword))
            return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"景点搜索失败: {e}")
        return json.dumps({"error": str(e), "city": city}, ensure_ascii=False)


def web_search(query: str) -> str:
    """通用网页搜索"""
    try:
        api = get_baidu_search()
        result = asyncio.run(api.search_generic(query))
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"网页搜索失败: {e}")
        return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)


def get_current_date() -> str:
    """获取当前日期"""
    try:
        client = get_mcp_client()
        date = client.get_current_date()
        return json.dumps({"current_date": date}, ensure_ascii=False)
    except Exception as e:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        return json.dumps({"current_date": date}, ensure_ascii=False)


def parse_date(date_text: str) -> str:
    """解析自然语言日期"""
    import re
    from datetime import datetime, timedelta
    
    try:
        today = datetime.now()
        today_weekday = today.weekday()
        weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekdays_short = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        text = date_text.strip()
        result_date = None
        
        if text in ["今天", "今日"]:
            result_date = today
        elif text in ["明天", "明日"]:
            result_date = today + timedelta(days=1)
        elif text in ["后天", "后日"]:
            result_date = today + timedelta(days=2)
        elif text in ["大后天", "大后日"]:
            result_date = today + timedelta(days=3)
        elif text in ["昨天", "昨日"]:
            result_date = today - timedelta(days=1)
        elif text in ["前天", "前日"]:
            result_date = today - timedelta(days=2)
        elif text.startswith("下周"):
            day_text = text[2:]
            target_weekday = next((i for i, w in enumerate(weekdays_short) if w in day_text), None)
            if target_weekday is not None:
                days_until = (target_weekday - today_weekday) % 7
                if days_until == 0:
                    days_until = 7
                result_date = today + timedelta(days=7 + days_until)
        elif text.startswith("本周") or text.startswith("这周"):
            day_text = text[2:] if text.startswith("本") else text[2:]
            target_weekday = next((i for i, w in enumerate(weekdays_short) if w in day_text), None)
            if target_weekday is not None:
                days_until = (target_weekday - today_weekday) % 7
                result_date = today + timedelta(days=days_until)
        elif text in weekdays_short:
            target_weekday = weekdays_short.index(text)
            days_until = (target_weekday - today_weekday) % 7
            if days_until == 0:
                days_until = 7
            result_date = today + timedelta(days=days_until)
        else:
            text_clean = text.replace("年", "-").replace("月", "-").replace("日", "").replace("号", "")
            match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text_clean)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                result_date = datetime(year, month, day)
            else:
                match = re.search(r"(\d{1,2})-(\d{1,2})", text_clean)
                if match:
                    month, day = int(match.group(1)), int(match.group(2))
                    year = today.year
                    if month < today.month:
                        year += 1
                    result_date = datetime(year, month, day)
        
        if result_date is None:
            return json.dumps({
                "original": date_text,
                "parsed": None,
                "error": f"无法解析日期: {date_text}"
            }, ensure_ascii=False)
        
        weekday_name = weekdays_cn[result_date.weekday()]
        return json.dumps({
            "original": date_text,
            "parsed": result_date.strftime("%Y-%m-%d"),
            "weekday": weekday_name
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        logger.error(f"日期解析失败: {e}")
        return json.dumps({
            "original": date_text,
            "parsed": None,
            "error": str(e)
        }, ensure_ascii=False)


def get_station_by_city(city: str) -> str:
    """查询城市附近的火车站"""
    try:
        api = get_baidu_search()
        try:
            result = asyncio.run(api.search_stations(city))
        except RuntimeError:
            result = asyncio.run(api.search_stations(city))
        
        stations = []
        results_list = result.get("results", [])
        
        if not results_list:
            return json.dumps({
                "city": city,
                "stations": [],
                "error": "未找到火车站信息"
            }, ensure_ascii=False)
        
        import re
        station_names = set()
        for item in results_list:
            title = item.get("标题", "")
            content = item.get("摘要", "")
            matches = re.findall(r'([^\s,，、]+站)', title + content)
            for match in matches:
                if len(match) >= 3:
                    station_names.add(match)
        
        recommended = None
        for name in list(station_names)[:10]:
            station_type = "火车站"
            if "高铁" in name or "东站" in name or "南站" in name:
                station_type = "高铁站"
            
            if recommended is None and station_type == "高铁站":
                recommended = name
            
            stations.append({"name": name, "type": station_type})
        
        if recommended is None and stations:
            recommended = stations[0]["name"]
        
        return json.dumps({
            "city": city,
            "stations": stations,
            "recommended": recommended,
            "count": len(stations)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"火车站查询失败: {e}")
        return json.dumps({
            "city": city,
            "stations": [],
            "error": str(e)
        }, ensure_ascii=False)


# 工具定义 - 简化版
AVAILABLE_TOOLS = {
    "get_weather": {
        "function": get_weather,
        "description": "查询指定城市的天气预报，包括温度、天气状况等。参数：city(城市名)",
    },
    "get_train_tickets": {
        "function": get_train_tickets,
        "description": "查询12306火车票。参数：date(日期YYYY-MM-DD)、from_station(出发站)、to_station(到达站)、train_type(G高铁/D动车)",
    },
    "search_attractions": {
        "function": search_attractions,
        "description": "搜索城市内的景点、美食。参数：city(城市名)、keyword(关键词)",
    },
    "web_search": {
        "function": web_search,
        "description": "通用网页搜索。参数：query(搜索关键词)",
    },
    "get_current_date": {
        "function": get_current_date,
        "description": "获取当前日期。无参数",
    },
    "parse_date": {
        "function": parse_date,
        "description": "解析自然语言日期。参数：date_text(如'明天'、'后天'、'下周一')",
    },
    "get_station_by_city": {
        "function": get_station_by_city,
        "description": "查询城市附近的火车站。参数：city(城市名)",
    }
}


def get_all_tools():
    """获取所有工具函数"""
    return [info["function"] for info in AVAILABLE_TOOLS.values()]


def execute_tool(tool_name: str, arguments: dict) -> str:
    """执行工具"""
    if tool_name in AVAILABLE_TOOLS:
        func = AVAILABLE_TOOLS[tool_name]["function"]
        try:
            # 普通函数调用
            if arguments:
                result = func(**arguments)
            else:
                # 无参函数
                result = func()
            return result if isinstance(result, str) else str(result)
        except TypeError as e:
            logger.error(f"工具参数错误: {e}")
            return json.dumps({"error": f"参数错误: {str(e)}"}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    else:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)