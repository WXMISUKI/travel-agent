"""
12306 MCP 客户端 - 整合现有MCP服务
"""
import requests
import json
from typing import Optional, Dict, List
import logging
from ..config import MCP_BASE_URL

logger = logging.getLogger(__name__)


class MCPClient:
    """12306 MCP 客户端"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or MCP_BASE_URL
    
    def _post(self, tool_name: str, params: dict = None) -> dict:
        """发送MCP请求"""
        try:
            resp = requests.post(
                f"{self.base_url}/tools/{tool_name}",
                json=params or {},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"MCP请求失败: {resp.status_code}")
                return {"error": f"请求失败: {resp.status_code}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"MCP请求异常: {e}")
            return {"error": str(e)}
    
    def get_current_date(self) -> str:
        """获取当前日期"""
        result = self._post("get-current-date")
        if result and "content" in result:
            return result["content"]
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def get_station_code(self, city: str) -> Optional[Dict]:
        """获取城市车站代码"""
        result = self._post("get-station-code-of-citys", {"city": city})
        return result
    
    def get_stations_in_city(self, city: str) -> List[Dict]:
        """获取城市内所有车站"""
        result = self._post("get-stations-code-in-city", {"city": city})
        return result.get("content", []) if result else []
    
    def get_station_by_name(self, station_name: str) -> Optional[Dict]:
        """通过车站名获取车站代码"""
        result = self._post("get-station-code-by-names", {"stationName": station_name})
        return result
    
    def get_tickets(self, date: str, from_station: str, 
                   to_station: str, train_type: str = "G") -> Dict:
        """查询火车票"""
        
        # 1. 获取车站代码
        from_codes = self.get_station_code(from_station)
        to_codes = self.get_station_code(to_station)
        
        if not from_codes or from_codes.get("error"):
            return {"error": f"无法找到出发站: {from_station}"}
        if not to_codes or to_codes.get("error"):
            return {"error": f"无法找到到达站: {to_station}"}
        
        # 取第一个车站
        from_code = list(from_codes.values())[0]["station_code"]
        to_code = list(to_codes.values())[0]["station_code"]
        
        # 2. 查询余票
        result = self._post("get-tickets", {
            "date": date,
            "fromStation": from_code,
            "toStation": to_code,
            "trainFilterFlags": train_type
        })
        
        return self._parse_tickets(result)
    
    def _parse_tickets(self, result: Dict) -> Dict:
        """解析车票数据"""
        if result.get("error"):
            return result
        
        content = result.get("content", "")
        if not content:
            return {"error": "未查询到车票数据", "tickets": []}
        
        # 简单解析返回内容
        lines = content.strip().split("\n") if isinstance(content, str) else [content]
        
        tickets = []
        for line in lines:
            if not line.strip():
                continue
            # 尝试解析车次信息
            if "G" in line or "D" in line or "K" in line or "T" in line or "Z" in line:
                tickets.append({"原始信息": line})
        
        return {
            "tickets": tickets,
            "原始内容": content
        }
    
    def get_train_route(self, train_no: str, from_station: str, 
                       to_station: str, date: str) -> Dict:
        """查询列车经停站"""
        
        # 获取车站代码
        from_codes = self.get_station_code(from_station)
        to_codes = self.get_station_code(to_station)
        
        if not from_codes or not to_codes:
            return {"error": "车站代码获取失败"}
        
        from_code = list(from_codes.values())[0]["station_code"]
        to_code = list(to_codes.values())[0]["station_code"]
        
        result = self._post("get-train-route-stations", {
            "trainNo": train_no,
            "fromStation": from_code,
            "toStation": to_code,
            "date": date
        })
        
        return result
