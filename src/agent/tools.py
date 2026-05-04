"""
LangChain Tools 定义 - 增强版
引入时间上下文管理和智能工具适配器
"""
import json
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
import re
import concurrent.futures
from ..data_sources.weather import OpenMeteoAPI
from ..data_sources.weather_api import get_weather_api as get_weather_api_new
from ..data_sources.mcp_client import MCPClient
from ..data_sources.baidu_search import BaiduSearchAPI
from ..data_sources.train_ticket import get_train_api
from ..data_sources.flight import get_flight_api
from ..utils.logger import logger
from .time_context import get_time_context, parse_date_with_context

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


def _run_async(async_fn, *args, **kwargs):
    """在同步上下文安全执行异步函数，兼容已运行事件循环场景"""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: asyncio.run(async_fn(*args, **kwargs)))
                return future.result()
    except RuntimeError:
        pass
    return asyncio.run(async_fn(*args, **kwargs))


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
    """查询指定城市的天气预报 - 使用 apihz.cn 15天预报接口
    
    Args:
        city: 城市名称（如"北京"、"上海"、"杭州"）
    
    Returns:
        JSON格式的天气数据
    """
    # 清理城市名
    city = city.replace("市", "").strip()
    
    # 第一尝试：使用 apihz.cn API
    try:
        api = get_weather_api_new()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, api.query_weather(city))
                    result = future.result()
            else:
                result = asyncio.run(api.query_weather(city))
        except RuntimeError:
            result = asyncio.run(api.query_weather(city))
        
        # 检查是否成功
        if isinstance(result, dict) and result.get("success"):
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        # 如果有错误，记录但继续fallback
        error_msg = result.get("error", "未知错误") if isinstance(result, dict) else str(result)
        logger.warning(f"apihz.cn 天气API失败: {error_msg}，尝试备用方案")
        
    except Exception as e:
        logger.warning(f"apihz.cn 天气API异常: {e}，尝试备用方案")
    
    # 第二尝试：使用 Open-Meteo API（开源免费）
    try:
        from ..data_sources.weather import OpenMeteoAPI
        open_meteo = OpenMeteoAPI()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, open_meteo.get_weather(city))
                    result = future.result()
            else:
                result = asyncio.run(open_meteo.get_weather(city))
        except RuntimeError:
            result = asyncio.run(open_meteo.get_weather(city))
        
        if isinstance(result, dict) and "error" not in result:
            result["source"] = "Open-Meteo"
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        logger.warning(f"Open-Meteo API 失败: {result.get('error') if isinstance(result, dict) else '未知错误'}")
        
    except Exception as e:
        logger.warning(f"Open-Meteo API 异常: {e}")
    
    # 最后尝试：使用百度搜索
    try:
        baidu_api = get_baidu_search()
        try:
            result = asyncio.run(baidu_api.search_weather(city))
            return json.dumps({
                "city": city,
                "source": "baidu_search",
                "results": result.get("results", [])[:5]
            }, ensure_ascii=False, indent=2)
        except RuntimeError:
            result = asyncio.run(baidu_api.search_weather(city))
            return json.dumps({
                "city": city,
                "source": "baidu_search",
                "results": result.get("results", [])[:5]
            }, ensure_ascii=False, indent=2)
    except Exception as e2:
        return json.dumps({"error": f"所有天气查询方式均失败: {str(e2)}", "city": city}, ensure_ascii=False)


def get_train_tickets(date: str, from_station: str, to_station: str, train_type: str = "G") -> str:
    """查询12306火车票 - 使用 apihz.cn API
    
    Args:
        date: 日期，格式 YYYY-MM-DD
        from_station: 出发站（如"绵阳"、"三明北"）
        to_station: 目的站（如"上海"、"宁波"）
        train_type: 火车类型（G高铁/D动车），仅用于过滤
    """
    try:
        # 清理站名
        from_station = from_station.replace("站", "").strip()
        to_station = to_station.replace("站", "").strip()
        
        # 使用新的 API
        api = get_train_api()
        
        # 异步调用
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, api.query_tickets(from_station, to_station, date))
                    result = future.result()
            else:
                result = asyncio.run(api.query_tickets(from_station, to_station, date))
        except RuntimeError:
            result = asyncio.run(api.query_tickets(from_station, to_station, date))
        
        # 过滤火车类型
        if result.get("tickets"):
            filtered_tickets = []
            for ticket in result["tickets"]:
                # 根据 train_type 过滤
                if train_type == "G" and not ticket.get("train_number", "").startswith("G"):
                    continue
                if train_type == "D" and not ticket.get("train_number", "").startswith("D"):
                    continue
                filtered_tickets.append(ticket)
            result["tickets"] = filtered_tickets
            result["count"] = len(filtered_tickets)
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"车票查询失败: {e}")
        return json.dumps({
            "error": str(e), 
            "from_station": from_station,
            "to_station": to_station
        }, ensure_ascii=False)


def get_flight_tickets(from_city: str, to_city: str, date: str) -> str:
    """查询航班机票信息 - 使用 apihz.cn API
    
    Args:
        from_city: 出发城市（如"北京"、"上海"）
        to_city: 目的城市（如"北京"、"杭州"）
        date: 日期，格式 YYYY-MM-DD
    """
    try:
        # 清理城市名
        from_city = from_city.replace("市", "").strip()
        to_city = to_city.replace("市", "").strip()
        
        # 使用机票 API
        api = get_flight_api()
        
        # 异步调用
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, api.query_flights(from_city, to_city, date))
                    result = future.result()
            else:
                result = asyncio.run(api.query_flights(from_city, to_city, date))
        except RuntimeError:
            result = asyncio.run(api.query_flights(from_city, to_city, date))
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"机票查询失败: {e}")
        return json.dumps({
            "error": str(e), 
            "from_city": from_city,
            "to_city": to_city
        }, ensure_ascii=False)


def search_attractions(city: str, keyword: str = "景点") -> str:
    """搜索城市内的景点、美食 - 使用百度搜索"""
    try:
        api = get_baidu_search()
        result = _run_async(api.search, city, keyword)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"景点搜索失败: {e}")
        return json.dumps({"error": str(e), "city": city}, ensure_ascii=False)


# 周边景点关键词模板
NEARBY_KEYWORD_TEMPLATES = {
    # 通用景点
    "景点": ["景点", "风景区", "旅游景区", "公园"],
    "景点推荐": ["景点", "风景区", "网红打卡点"],
    
    # 亲子
    "亲子": ["亲子乐园", "儿童乐园", "游乐场", "动物园"],
    "遛娃": ["亲子乐园", "儿童乐园", "游乐场"],
    
    # 文化
    "博物馆": ["博物馆", "纪念馆", "展览馆", "美术馆"],
    "历史": ["博物馆", "纪念馆", "历史古迹"],
    "文化": ["博物馆", "展览馆", "文化广场"],
    
    # 自然
    "自然": ["自然风景区", "森林公园", "山水景点"],
    "爬山": ["山", "森林公园", "登山"],
    
    # 美食
    "美食": ["特色美食", "餐厅", "小吃街", "夜市"],
    "餐厅": ["餐厅", "饭店", "特色小吃"],
    "小吃": ["小吃街", "夜市", "美食广场"],
    
    # 休闲
    "休闲": ["休闲广场", "商场", "步行街"],
    "购物": ["商场", "购物中心", "步行街"],
    
    # 住宿
    "酒店": ["酒店", "民宿", "宾馆"],
    "住宿": ["酒店", "民宿", "旅馆"],
    
    # 娱乐
    "娱乐": ["KTV", "电影院", "电玩城", "酒吧"],
    "看电影": ["电影院", "影城"],
}

# 默认关键词列表（按优先级）
DEFAULT_KEYWORDS = ["景点", "风景区", "公园", "网红打卡点"]


def _expand_keywords(keyword: str) -> List[str]:
    """扩展关键词为搜索词列表
    
    Args:
        keyword: 用户输入的关键词
    
    Returns:
        扩展后的关键词列表
    """
    # 精确匹配
    if keyword in NEARBY_KEYWORD_TEMPLATES:
        return NEARBY_KEYWORD_TEMPLATES[keyword]
    
    # 模糊匹配
    for template_key, keywords in NEARBY_KEYWORD_TEMPLATES.items():
        if keyword in template_key or template_key in keyword:
            return keywords
    
    # 返回默认
    return DEFAULT_KEYWORDS if keyword == "景点" else [keyword]


def _merge_attractions(results_list: List[Dict], max_count: int = 15) -> List[Dict]:
    """合并多个关键词的搜索结果，去重并按距离排序
    
    Args:
        results_list: 多个搜索结果列表
        max_count: 最大返回数量
    
    Returns:
        合并后的景点列表
    """
    seen_names = set()
    merged = []
    
    for results in results_list:
        for item in results:
            name = item.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                
                # 解析距离
                distance = item.get("distance", "")
                try:
                    # 距离可能是 "500m" 或数字
                    if isinstance(distance, str) and "m" in distance:
                        distance_val = int(distance.replace("m", ""))
                    else:
                        distance_val = int(distance) if distance else 999999
                except:
                    distance_val = 999999
                
                item["_distance_val"] = distance_val
                merged.append(item)
    
    # 按距离排序
    merged.sort(key=lambda x: x.get("_distance_val", 999999))
    
    # 移除临时字段
    for item in merged:
        item.pop("_distance_val", None)
    
    return merged[:max_count]


def search_nearby_attractions(city: str, keyword: str = "景点", radius: int = 5000) -> str:
    """搜索城市周边景点 - 增强版
    
    特点：
    1. 智能关键词扩展
    2. 多关键词搜索合并
    3. 按距离排序，优先返回近的景点
    
    Args:
        city: 城市名（如"杭州"、"北京"）
        keyword: 关键词（默认"景点"），支持智能扩展
        radius: 查询半径（米），默认5公里
    
    Returns:
        JSON格式的周边景点列表
    """
    # 扩展关键词
    expanded_keywords = _expand_keywords(keyword)
    logger.info(f"周边景点搜索关键词扩展: {keyword} -> {expanded_keywords}")
    
    # 优先使用 apihz.cn API（支持多关键词）
    try:
        from ..data_sources.nearby import query_attractions
        
        all_results = []
        
        for kw in expanded_keywords[:3]:  # 最多搜索3个关键词
            try:
                result = query_attractions(city, kw, radius)
                if result.get("success") and result.get("attractions"):
                    all_results.append(result["attractions"])
                    logger.info(f"关键词 '{kw}' 获取到 {len(result['attractions'])} 个结果")
            except Exception as e:
                logger.warning(f"关键词 '{kw}' 搜索失败: {e}")
                continue
        
        # 合并结果
        if all_results:
            merged = _merge_attractions(all_results)
            
            return json.dumps({
                "success": True,
                "city": city,
                "keyword": keyword,
                "expanded_keywords": expanded_keywords,
                "radius": radius,
                "count": len(merged),
                "attractions": merged,
                "source": "apihz_api"
            }, ensure_ascii=False, indent=2)
        
        # 所有关键词都失败
        raise Exception("所有关键词搜索失败")
            
    except Exception as e:
        # 备用：使用百度搜索
        logger.warning(f"周边景点API失败，使用百度搜索备用: {e}")
        
        try:
            api = get_baidu_search()
            # 使用第一个关键词搜索
            result = _run_async(api.search, city, expanded_keywords[0])
            
            attractions = []
            for item in result.get("results", [])[:10]:
                attractions.append({
                    "name": item.get("标题", ""),
                    "address": item.get("摘要", ""),
                    "distance": "",
                    "type": keyword
                })
            
            return json.dumps({
                "success": True,
                "city": city,
                "keyword": keyword,
                "expanded_keywords": expanded_keywords,
                "count": len(attractions),
                "attractions": attractions,
                "source": "baidu_search"
            }, ensure_ascii=False, indent=2)
            
        except Exception as e2:
            logger.error(f"周边景点搜索失败: {e2}")
            return json.dumps({"error": str(e2), "city": city}, ensure_ascii=False)


def web_search(query: str) -> str:
    """通用网页搜索"""
    try:
        api = get_baidu_search()
        result = _run_async(api.search_generic, query)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"网页搜索失败: {e}")
        return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)


def get_current_date() -> str:
    """获取当前日期 - 使用时间上下文"""
    try:
        context = get_time_context()
        return json.dumps({
            "current_date": context.get_today(),
            "formatted": context.get_today_formatted(),
            "source": "time_context"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取当前日期失败: {e}")
        # 后备方案 - 使用中国时区
        from datetime import timezone, timedelta
        china_tz = timezone(timedelta(hours=8))
        now = datetime.now(china_tz)
        return json.dumps({
            "current_date": now.strftime("%Y-%m-%d"),
            "formatted": f"{now.month}月{now.day}日 星期{['一','二','三','四','五','六','日'][now.weekday()]}",
            "source": "fallback"
        }, ensure_ascii=False, indent=2)


def capability_info(query: str = "") -> str:
    """返回智能体的能力信息"""
    capabilities = {
        "功能": [
            "�️ 火车票查询 - 查询12306火车票余票信息",
            "🌤️ 天气查询 - 查询指定城市15天天气预报",
            "🎯 景点推荐 - 推荐热门景点和美食",
            "🔍 智能搜索 - 回答各类旅行相关问题",
            "📅 日期解析 - 理解明天、后天等相对日期"
        ],
        "使用示例": [
            "帮我查一下明天北京到上海的高铁票",
            "后天杭州天气怎么样",
            "上海有什么好玩的地方",
            "帮我规划一个去厦门的三天两夜旅行"
        ],
        "特点": [
            "支持相对日期：明天、后天、下周等",
            "支持高铁、动车、普通车查询",
            "支持15天天气预报",
            "智能推荐周边景点和美食"
        ]
    }
    
    return json.dumps({
        "type": "capability_info",
        "capabilities": capabilities,
        "message": "您好！我是旅行规划助手，可以为您提供以下服务："
    }, ensure_ascii=False, indent=2)


def parse_date(date_text: str) -> str:
    """解析自然语言日期 - 增强版
    
    支持：明天、后天、下周一、3月15日、周末等
    """
    try:
        text = (date_text or "").strip()

        # 先处理“时长表达”如：三天两夜、2天1夜、三日游
        duration_match = re.search(r"([一二两三四五六七八九十\d]+)\s*(天|日)\s*([一二两三四五六七八九十\d]+)?\s*夜?", text)
        if duration_match:
            def cn_to_int(token: str) -> int:
                token = token.strip()
                if token.isdigit():
                    return int(token)
                mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                if token == "十":
                    return 10
                if token.startswith("十") and len(token) == 2:
                    return 10 + mapping.get(token[1], 0)
                if token.endswith("十") and len(token) == 2:
                    return mapping.get(token[0], 1) * 10
                if len(token) == 2 and token[0] in mapping and token[1] in mapping and token[1] != "十":
                    return mapping[token[0]] * 10 + mapping[token[1]]
                return mapping.get(token, 0)

            days = cn_to_int(duration_match.group(1))
            nights = cn_to_int(duration_match.group(3)) if duration_match.group(3) else max(days - 1, 0)

            context = get_time_context()
            start_date = context.get_today()
            return json.dumps({
                "original": text,
                "parsed": start_date,
                "weekday": context.get_today_formatted().split()[-1],
                "days_from_today": 0,
                "is_past": False,
                "duration_days": days,
                "duration_nights": nights,
                "date_type": "duration"
            }, ensure_ascii=False, indent=2)

        # 使用时间上下文解析
        result = parse_date_with_context(text)
        
        if result is None:
            return json.dumps({
                "original": date_text,
                "parsed": None,
                "error": f"无法解析日期: {date_text}"
            }, ensure_ascii=False, indent=2)
        
        if "error" in result:
            return json.dumps({
                "original": date_text,
                "parsed": None,
                "error": result.get("error")
            }, ensure_ascii=False, indent=2)
        
        return json.dumps({
            "original": date_text,
            "parsed": result.get("parsed"),
            "weekday": result.get("weekday"),
            "days_from_today": result.get("days_from_today", 0),
            "is_past": result.get("is_past", False)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"日期解析失败: {e}")
        return json.dumps({
            "original": date_text,
            "parsed": None,
            "error": str(e)
        }, ensure_ascii=False)


def get_station_by_city(city: str) -> str:
    """查询城市附近的火车站 - 增强版
    
    返回标准化的火车站列表，包含：
    - name: 站名
    - type: 站类型（高铁站/火车站）
    - code: 站代码（如果能获取）
    """
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
                "error": f"未找到{city}的火车站信息",
                "suggestion": "请尝试使用更通用的城市名"
            }, ensure_ascii=False)
        
        import re
        station_names = set()
        
        # 从搜索结果中提取站名
        for item in results_list:
            title = item.get("标题", "")
            content = item.get("摘要", "")
            
            # 匹配各种站名格式
            # 1. XX站 格式 - 改进正则，排除杂质
            matches = re.findall(r'([^\s,，、。;；："\']{2,6}站)', title + content)
            for match in matches:
                # 过滤明显不是站名的
                skip_words = ["网站", "官网", "售票", "电话", "地址", "查询", "附近", 
                             "时刻表", "班次", "车次", "出发", "到达", "铁路", "分享",
                             "怎么", "如何", "多少", "多久", "预订", "APP", "微信",
                             "微博", "抖音", "小红书", "热门", "推荐", "攻略", "旅游"]
                if any(skip in match for skip in skip_words):
                    continue
                
                # 过滤包含标点符号的（说明是截取的杂质）
                if any(p in match for p in [":", "！", "？", "。", "，", "、", "；", '"', "'"]):
                    continue
                
                # 过滤太短的或明显是乱码的
                if len(match) < 3:
                    continue
                    
                station_names.add(match)
        
        # 进一步过滤：只保留以城市名开头或包含常见城市后缀的站名
        valid_stations = set()
        for name in station_names:
            # 检查是否是有效的站名
            # 有效站名格式：XXX站、XXX北站、XXX南站、XXX东站、XXX西站
            if re.match(r'^[^\s,，、。;；："\']+[东南西北]?站$', name):
                valid_stations.add(name)
            elif name.endswith("站") and len(name) >= 3:
                # 检查是否包含有效的城市名
                valid_cities = ["北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", 
                               "成都", "重庆", "西安", "福州", "厦门", "宁波", "温州",
                               "三明", "泉州", "漳州", "龙岩", "南平", "宁德", "莆田"]
                if any(city in name for city in valid_cities):
                    valid_stations.add(name)
        
        station_names = valid_stations if valid_stations else station_names
        
        # 如果没有提取到站名，尝试从城市名推断
        if not station_names:
            # 常见高铁站映射
            common_stations = {
                "沙县": ["三明北站", "沙县站"],
                "宁波": ["宁波站", "宁波东站"],
                "福州": ["福州站", "福州南站"],
                "厦门": ["厦门站", "厦门北站"],
                "杭州": ["杭州站", "杭州东站"],
                "上海": ["上海站", "上海虹桥站"],
                "北京": ["北京站", "北京南站", "北京西站"],
            }
            for key, fallback in common_stations.items():
                if key in city:
                    station_names = set(fallback)
                    break
        
        # 构建标准化的站点列表
        valid_stations_list = []
        for name in list(station_names)[:15]:
            # 判断站类型
            station_type = "火车站"
            if any(t in name for t in ["高铁", "东站", "南站", "北站"]):
                station_type = "高铁站"
            
            valid_stations_list.append({
                "name": name,
                "type": station_type,
                "city": city
            })
        
        # 智能推荐首选站
        recommended = None
        
        # 策略1：优先选择与城市名匹配的站点
        for s in valid_stations_list:
            # 如果站名包含城市名，选择它
            if city in s["name"]:
                recommended = s["name"]
                break
        
        # 策略2：如果没有匹配的，选择高铁站
        if recommended is None:
            for s in valid_stations_list:
                if s["type"] == "高铁站":
                    recommended = s["name"]
                    break
        
        # 策略3：选择第一个
        if recommended is None and valid_stations_list:
            recommended = valid_stations_list[0]["name"]
        
        stations = valid_stations_list[:10]
        
        return json.dumps({
            "city": city,
            "stations": stations,
            "recommended": recommended,
            "count": len(stations),
            "status": "success"
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
        "description": "查询12306火车票余票和票价。参数：date(日期YYYY-MM-DD)、from_station(出发站)、to_station(到达站)、train_type(G高铁/D动车)",
    },
    "get_flight_tickets": {
        "function": get_flight_tickets,
        "description": "查询航班机票信息。参数：from_city(出发城市)、to_city(目的城市)、date(日期YYYY-MM-DD)",
    },
    "search_attractions": {
        "function": search_attractions,
        "description": "搜索城市内的景点、美食。参数：city(城市名)、keyword(关键词)",
    },
    "search_nearby_attractions": {
        "function": search_nearby_attractions,
        "description": "搜索城市周边景点、美食、酒店等。参数：city(城市名)、keyword(关键词，默认景点)",
    },
    "web_search": {
        "function": web_search,
        "description": "通用网页搜索。参数：query(搜索关键词)",
    },
    "get_current_date": {
        "function": get_current_date,
        "description": "获取当前日期。无参数",
    },
    "capability_info": {
        "function": capability_info,
        "description": "查询智能体能力。参数：query(可选，用户查询内容)",
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


# 工具重试配置
TOOL_RETRY_CONFIG = {
    "max_retries": 2,  # 最大重试次数
    "retry_delay": 0.5,  # 重试延迟（秒）
    # 特定工具的重试配置
    "get_train_tickets": {
        "max_retries": 3,
        "fix_params_on_retry": True  # 是否尝试修复参数
    },
    "get_weather": {
        "max_retries": 2,
        "fix_params_on_retry": False
    },
    "search_nearby_attractions": {
        "max_retries": 2,
        "fix_params_on_retry": False
    }
}


def _fix_tool_params(tool_name: str, params: dict, error: str) -> Optional[dict]:
    """尝试修复工具参数
    
    Args:
        tool_name: 工具名称
        params: 原始参数
        error: 错误信息
    
    Returns:
        修复后的参数，如果无法修复则返回None
    """
    fixed_params = params.copy()
    
    if tool_name == "get_train_tickets":
        # 尝试修复站名
        if "无法找到出发站" in error or "出发站" in error:
            if "from_station" in fixed_params:
                station = fixed_params["from_station"]
                # 去掉"县"改为"市"
                if "县" in station:
                    fixed_params["from_station"] = station.replace("县", "市")
                # 去掉"站"字
                elif station.endswith("站"):
                    fixed_params["from_station"] = station[:-1]
                logger.info(f"修复出发站: {station} -> {fixed_params['from_station']}")
                return fixed_params
        
        if "无法找到到达站" in error or "到达站" in error:
            if "to_station" in fixed_params:
                station = fixed_params["to_station"]
                if "县" in station:
                    fixed_params["to_station"] = station.replace("县", "市")
                elif station.endswith("站"):
                    fixed_params["to_station"] = station[:-1]
                logger.info(f"修复到达站: {station} -> {fixed_params['to_station']}")
                return fixed_params
    
    elif tool_name == "get_weather":
        # 尝试修复城市名
        if "city" in fixed_params:
            city = fixed_params["city"]
            # 去掉市、区、县等后缀
            for suffix in ["市", "区", "县"]:
                if city.endswith(suffix) and len(city) > 2:
                    fixed_params["city"] = city[:-1]
                    logger.info(f"修复城市名: {city} -> {fixed_params['city']}")
                    return fixed_params
    
    return None


def _is_error_result(result: str) -> bool:
    """检查工具返回是否表示错误
    
    Args:
        result: 工具返回的结果
    
    Returns:
        True表示错误，False表示正常
    """
    try:
        data = json.loads(result)
        # 检查各种错误情况
        if isinstance(data, dict):
            if "error" in data:
                return True
            if data.get("status") == "error":
                return True
            if data.get("success") is False:
                return True
        return False
    except:
        # 无法解析也视为错误
        return True


def execute_tool_with_retry(tool_name: str, arguments: dict) -> str:
    """带重试机制的工具执行
    
    特点：
    1. 自动根据配置重试
    2. 尝试自动修复参数
    3. 记录重试日志
    
    Args:
        tool_name: 工具名称
        arguments: 工具参数
    
    Returns:
        工具执行结果
    """
    import time
    
    # 获取重试配置
    config = TOOL_RETRY_CONFIG.get(tool_name, {})
    max_retries = config.get("max_retries", TOOL_RETRY_CONFIG["max_retries"])
    retry_delay = config.get("retry_delay", TOOL_RETRY_CONFIG["retry_delay"])
    fix_params_on_retry = config.get("fix_params_on_retry", False)
    
    last_error = None
    current_params = arguments.copy()
    
    for attempt in range(max_retries + 1):
        try:
            # 直接调用工具函数，避免循环递归
            if tool_name not in AVAILABLE_TOOLS:
                return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
            
            func = AVAILABLE_TOOLS[tool_name]["function"]
            try:
                if current_params:
                    result = func(**current_params)
                else:
                    result = func()
                result = result if isinstance(result, str) else str(result)
            except TypeError as e:
                logger.error(f"工具参数错误: {e}")
                result = json.dumps({"error": f"参数错误: {str(e)}"}, ensure_ascii=False)
            except Exception as e:
                logger.error(f"工具执行失败: {e}")
                result = json.dumps({"error": str(e)}, ensure_ascii=False)
            
            # 检查结果是否为错误
            if not _is_error_result(result):
                if attempt > 0:
                    logger.info(f"工具 {tool_name} 第 {attempt + 1} 次尝试成功")
                return result
            
            # 解析错误信息
            try:
                error_data = json.loads(result)
                error_msg = error_data.get("error", str(result))
            except:
                error_msg = str(result)
            
            last_error = error_msg
            logger.warning(f"工具 {tool_name} 第 {attempt + 1} 次尝试失败: {error_msg[:100]}")
            
            # 尝试修复参数
            if fix_params_on_retry and attempt < max_retries:
                fixed = _fix_tool_params(tool_name, current_params, error_msg)
                if fixed:
                    current_params = fixed
                    logger.info(f"尝试修复参数后重试: {current_params}")
            
            # 等待后重试
            if attempt < max_retries:
                time.sleep(retry_delay)
                
        except Exception as e:
            last_error = str(e)
            logger.error(f"工具 {tool_name} 执行异常: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                break
    
    # 所有重试都失败，返回最后一次的错误结果
    return json.dumps({
        "error": f"工具执行失败，已重试 {max_retries + 1} 次: {last_error}",
        "tool": tool_name,
        "params": arguments
    }, ensure_ascii=False)


def execute_tool_raw(tool_name: str, arguments: dict) -> str:
    """原始工具执行（无重试）"""
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


def execute_tool(tool_name: str, arguments: dict) -> str:
    """执行工具 - 带重试机制
    
    使用 execute_tool_with_retry 实现自动重试和参数修复
    """
    return execute_tool_with_retry(tool_name, arguments)
