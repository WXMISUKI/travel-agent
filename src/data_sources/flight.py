"""
机票查询 API - 基于 apihz.cn 服务
支持航班查询
"""
import json
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from ..utils.logger import logger


# API 配置
API_USER_ID = "10013949"
API_KEY = "9c8a62dfe79ed9bb426a16926f019509"

# 备用接口列表
BACKUP_APIS = [
    "http://101.35.2.25/api/dingzhi/jipiaolist.php",
    "http://124.222.204.22/api/dingzhi/jipiaolist.php",
    "http://81.68.149.132/api/dingzhi/jipiaolist.php"
]

# 获取最优接口的API
API_DISCOVERY_URL = "https://cn.apihz.cn/api/dingzhi/jipiaolist.php"

# 城市到机场代码映射
AIRPORT_MAP = {
    # 直辖市
    "北京": {"code": "PEK", "name": "北京首都"},
    "上海": {"code": "PVG", "name": "上海浦东"},
    "天津": {"code": "TSN", "name": "天津滨海"},
    "重庆": {"code": "CKG", "name": "重庆江北"},
    
    # 主要城市
    "广州": {"code": "CAN", "name": "广州白云"},
    "深圳": {"code": "SZX", "name": "深圳宝安"},
    "成都": {"code": "CTU", "name": "成都双流"},
    "杭州": {"code": "HGH", "name": "杭州萧山"},
    "南京": {"code": "NKG", "name": "南京禄口"},
    "武汉": {"code": "WUH", "name": "武汉天河"},
    "西安": {"code": "XIY", "name": "西安咸阳"},
    "长沙": {"code": "CSX", "name": "长沙黄花"},
    "郑州": {"code": "CGO", "name": "郑州新郑"},
    "济南": {"code": "TNA", "name": "济南遥墙"},
    "青岛": {"code": "TAO", "name": "青岛流亭"},
    "厦门": {"code": "XMN", "name": "厦门高崎"},
    "福州": {"code": "FOC", "name": "福州长乐"},
    "宁波": {"code": "NGB", "name": "宁波栎社"},
    "温州": {"code": "WNZ", "name": "温州龙湾"},
    "沈阳": {"code": "SHE", "name": "沈阳桃仙"},
    "大连": {"code": "DLC", "name": "大连周水子"},
    "哈尔滨": {"code": "HRB", "name": "哈尔滨太平"},
    "长春": {"code": "CGQ", "name": "长春龙嘉"},
    "石家庄": {"code": "SJW", "name": "石家庄正定"},
    "太原": {"code": "TYN", "name": "太原武宿"},
    "昆明": {"code": "KMG", "name": "昆明长水"},
    "贵阳": {"code": "KWE", "name": "贵阳龙洞堡"},
    "南宁": {"code": "NNG", "name": "南宁吴圩"},
    "海口": {"code": "HAK", "name": "海口美兰"},
    "乌鲁木齐": {"code": "URC", "name": "乌鲁木齐地窝堡"},
    "兰州": {"code": "LHW", "name": "兰州中川"},
    "银川": {"code": "INC", "name": "银川河东"},
    "西宁": {"code": "XNN", "name": "西宁曹家堡"},
    "拉萨": {"code": "LXA", "name": "拉萨贡嘎"},
    "呼和浩特": {"code": "HET", "name": "呼和浩特白塔"},
    "三明": {"code": "TXN", "name": "三明沙县"},
}


class FlightAPI:
    """机票查询 API 客户端"""
    
    def __init__(self):
        self._cached_api = None
        self._cache_time = 0
        self._cache_ttl = 3600  # 缓存1小时
    
    def _get_airport_code(self, city: str) -> str:
        """根据城市名获取机场代码"""
        city = city.replace("市", "").strip()
        
        # 直接匹配
        if city in AIRPORT_MAP:
            return AIRPORT_MAP[city]["code"]
        
        # 模糊匹配
        for key, value in AIRPORT_MAP.items():
            if city in key or key in city:
                return value["code"]
        
        # 默认返回城市名，让API自己解析
        return city
    
    async def _get_best_api(self) -> str:
        """获取最优 API 接口地址（带缓存）"""
        now = time.time()
        
        # 检查缓存
        if self._cached_api and (now - self._cache_time) < self._cache_ttl:
            return self._cached_api
        
        # 尝试备用接口
        for api in BACKUP_APIS:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{api}?id={API_USER_ID}&key={API_KEY}&star=上海&end=北京&stary=2026&starm=3&stard=20"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("code") in [200, 400]:
                                self._cached_api = api
                                self._cache_time = now
                                logger.info(f"使用机票接口: {api}")
                                return api
            except:
                continue
        
        # 如果都失败，使用默认
        self._cached_api = BACKUP_APIS[0]
        return self._cached_api
    
    async def query_flights(self, from_city: str, to_city: str, 
                          date: str) -> Dict[str, Any]:
        """
        查询航班机票
        
        Args:
            from_city: 出发城市（如"北京"、"上海"）
            to_city: 目的城市（如"北京"、"杭州"）
            date: 日期，格式 "YYYY-MM-DD"
        
        Returns:
            标准化的航班数据
        """
        # 解析日期
        try:
            parts = date.split("-")
            year = parts[0]
            month = parts[1]
            day = parts[2]
        except:
            year = "2026"
            month = "03"
            day = "15"
        
        # 获取机场代码
        from_code = self._get_airport_code(from_city)
        to_code = self._get_airport_code(to_city)
        
        # 获取最优接口
        api_url = await self._get_best_api()
        
        try:
            # 构建请求
            url = f"{api_url}?id={API_USER_ID}&key={API_KEY}&star={from_code}&end={to_code}&stary={year}&starm={month}&stard={day}&type=1"
            
            logger.info(f"请求机票API: {url[:100]}...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return {
                            "error": f"HTTP {resp.status}",
                            "from_city": from_city,
                            "to_city": to_city,
                            "date": date
                        }
                    
                    data = await resp.json()
                    return self._parse_response(data, from_city, to_city, date)
                    
        except asyncio.TimeoutError:
            logger.error("机票API请求超时")
            return {
                "error": "请求超时",
                "from_city": from_city,
                "to_city": to_city,
                "date": date
            }
        except Exception as e:
            logger.error(f"机票API请求失败: {e}")
            return {
                "error": str(e),
                "from_city": from_city,
                "to_city": to_city,
                "date": date
            }
    
    def _parse_response(self, data: Dict, from_city: str, 
                     to_city: str, date: str) -> Dict:
        """解析API响应"""
        
        if data.get("code") != 200:
            error_msg = data.get("msg", "未知错误")
            return {
                "error": error_msg,
                "from_city": from_city,
                "to_city": to_city,
                "date": date,
                "flights": []
            }
        
        # 解析航班数据
        flights = []
        datas = data.get("datas", [])
        
        for item in datas:
            flight = {
                "flight_number": item.get("fno", ""),
                "airline": item.get("airlinename", ""),
                "departure_time": item.get("flystartime", ""),
                "arrival_time": item.get("flyendtime", ""),
                "duration": item.get("flytime", ""),
                "departure_airport": f"{item.get('starairname', '')}{item.get('starpoint', '')}",
                "arrival_airport": f"{item.get('endairname', '')}{item.get('endpoint', '')}",
                "plane_type": item.get("fjmodel", ""),
                "punctuality": item.get("zdl", ""),
                "prices": {
                    "economy": self._format_price(item.get("jc", "0")),
                    "economy_discount": item.get("jczk", ""),
                    "business": self._format_price(item.get("gc", "0")),
                    "business_discount": item.get("gczk", "")
                },
                "meals": item.get("can", "无"),
                "cancel_rate": item.get("clp", "")
            }
            flights.append(flight)
        
        return {
            "success": True,
            "from_city": data.get("starnamecn", from_city),
            "to_city": data.get("endnamecn", to_city),
            "date": date,
            "count": len(flights),
            "flights": flights
        }
    
    def _format_price(self, price: str) -> str:
        """格式化票价"""
        try:
            p = float(price)
            if p == 0:
                return "无"
            return f"¥{int(p)}"
        except:
            return price


# 全局实例
_flight_api = None


def get_flight_api() -> FlightAPI:
    """获取机票API实例"""
    global _flight_api
    if _flight_api is None:
        _flight_api = FlightAPI()
    return _flight_api
