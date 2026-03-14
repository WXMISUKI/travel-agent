"""
火车票查询 API - 基于 apihz.cn 服务
支持自动获取最优接口和余票查询
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
    "http://101.35.2.25/api/12306/api4.php",
    "http://124.222.204.22/api/12306/api4.php",
    "http://81.68.149.132/api/12306/api4.php"
]

# 获取最优接口的API
API_DISCOVERY_URL = "https://cn.apihz.cn/api/12306/api4.php"


class TrainTicketAPI:
    """火车票查询 API 客户端"""
    
    def __init__(self):
        self._cached_api = None
        self._cache_time = 0
        self._cache_ttl = 60  # 缓存60秒
    
    async def _get_best_api(self) -> str:
        """获取最优 API 接口地址（带缓存）"""
        now = time.time()
        
        # 检查缓存
        if self._cached_api and (now - self._cache_time) < self._cache_ttl:
            return self._cached_api
        
        # 尝试获取最优接口
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{API_DISCOVERY_URL}?id={API_USER_ID}&key={API_KEY}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 200:
                            api_url = data.get("api", "")
                            if api_url:
                                self._cached_api = api_url
                                self._cache_time = now
                                logger.info(f"获取到最优接口: {api_url}")
                                return api_url
        except Exception as e:
            logger.warning(f"获取最优接口失败: {e}，使用备用接口")
        
        # 尝试备用接口
        for api in BACKUP_APIS:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{api}?id={API_USER_ID}&key={API_KEY}&add=测试&end=北京&y=2026&m=3&d=15"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("code") in [200, 400]:  # 400也说明接口可用
                                self._cached_api = api
                                self._cache_time = now
                                logger.info(f"使用备用接口: {api}")
                                return api
            except:
                continue
        
        # 如果都失败，使用默认
        self._cached_api = BACKUP_APIS[0]
        return self._cached_api
    
    async def query_tickets(self, from_station: str, to_station: str, 
                          date: str) -> Dict[str, Any]:
        """
        查询火车票
        
        Args:
            from_station: 出发站（如"绵阳"、"三明北"）
            to_station: 目的站（如"上海"、"宁波"）
            date: 日期，格式 "YYYY-MM-DD" 或 "2026-03-15"
        
        Returns:
            标准化的火车票数据
        """
        # 解析日期
        try:
            # 支持 YYYY-MM-DD 格式
            if "-" in date:
                parts = date.split("-")
                year = parts[0]
                month = parts[1]
                day = parts[2]
            else:
                year = date[:4]
                month = date[4:6]
                day = date[6:8]
        except:
            year = "2026"
            month = "03"
            day = "15"
        
        # 获取最优接口
        api_url = await self._get_best_api()
        
        try:
            # 构建请求
            url = f"{api_url}?id={API_USER_ID}&key={API_KEY}&add={from_station}&end={to_station}&y={year}&m={month}&d={day}"
            
            logger.info(f"请求火车票API: {url[:100]}...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return {
                            "error": f"HTTP {resp.status}",
                            "from_station": from_station,
                            "to_station": to_station,
                            "date": date
                        }
                    
                    data = await resp.json()
                    return self._parse_response(data, from_station, to_station, date)
                    
        except asyncio.TimeoutError:
            logger.error("火车票API请求超时")
            return {
                "error": "请求超时",
                "from_station": from_station,
                "to_station": to_station,
                "date": date
            }
        except Exception as e:
            logger.error(f"火车票API请求失败: {e}")
            return {
                "error": str(e),
                "from_station": from_station,
                "to_station": to_station,
                "date": date
            }
    
    def _parse_response(self, data: Dict, from_station: str, 
                       to_station: str, date: str) -> Dict:
        """解析API响应"""
        
        if data.get("code") != 200:
            error_msg = data.get("msg", "未知错误")
            return {
                "error": error_msg,
                "from_station": from_station,
                "to_station": to_station,
                "date": date,
                "tickets": []
            }
        
        # 解析车次数据
        tickets = []
        datas = data.get("datas", [])
        
        for item in datas:
            ticket = {
                "train_number": item.get("train_order", ""),  # 车次
                "train_type": item.get("train_type", ""),     # 列车类型
                "from_station": item.get("depart_name", ""),  # 出发站
                "to_station": item.get("arrive_name", ""),    # 到达站
                "depart_time": item.get("depart_time", ""),   # 出发时间
                "arrive_time": item.get("arrive_time", ""),   # 到达时间
                "duration": item.get("alltime", ""),          # 乘车时长
                "day_difference": item.get("day_difference", "0"),  # 天数差
                "seats": {
                    "二等座": self._format_price(item.get("edz", "0")),
                    "一等座": self._format_price(item.get("ydz", "0")),
                    "商务座": self._format_price(item.get("tdz", "0")),
                    "硬座": self._format_price(item.get("yz", "0")),
                    "硬卧": self._format_price(item.get("yw", "0")),
                    "软卧": self._format_price(item.get("rw", "0"))
                }
            }
            tickets.append(ticket)
        
        return {
            "success": True,
            "from_station": from_station,
            "to_station": to_station,
            "date": date,
            "count": len(tickets),
            "tickets": tickets
        }
    
    def _format_price(self, price: str) -> str:
        """格式化票价"""
        try:
            p = float(price)
            if p == 0:
                return "无"
            return f"¥{p:.2f}"
        except:
            return price


# 全局实例
_train_api = None


def get_train_api() -> TrainTicketAPI:
    """获取火车票API实例"""
    global _train_api
    if _train_api is None:
        _train_api = TrainTicketAPI()
    return _train_api
