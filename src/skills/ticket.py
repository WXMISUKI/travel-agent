"""
车票查询 Skill
"""
from typing import Dict
from .base import BaseSkill, SkillInput, SkillOutput
from ..data_sources.mcp_client import MCPClient


class TicketSkill(BaseSkill):
    """车票查询 Skill"""
    
    name = "ticket"
    description = "查询火车票信息"
    
    def __init__(self):
        self.mcp_client = MCPClient()
    
    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """执行车票查询"""
        try:
            params = input_data.get("query_params", {})
            date = params.get("date")
            from_station = params.get("from_station")
            to_station = params.get("to_station")
            train_type = params.get("train_type", "G")
            
            if not date:
                return self._create_error_output("缺少出发日期参数")
            if not from_station:
                return self._create_error_output("缺少出发地参数")
            if not to_station:
                return self._create_error_output("缺少目的地参数")
            
            # 调用12306 MCP
            data = self.mcp_client.get_tickets(
                date=date,
                from_station=from_station,
                to_station=to_station,
                train_type=train_type
            )
            
            if data.get("error"):
                return self._create_error_output(data["error"])
            
            return self._create_success_output(data)
            
        except Exception as e:
            return self._create_error_output(f"车票查询失败: {str(e)}")
    
    def get_tickets_sync(self, date: str, from_station: str, 
                        to_station: str, train_type: str = "G") -> Dict:
        """同步获取车票（供Tool调用）"""
        try:
            return self.mcp_client.get_tickets(date, from_station, to_station, train_type)
        except Exception as e:
            return {"error": str(e)}
    
    def get_current_date(self) -> str:
        """获取当前日期"""
        return self.mcp_client.get_current_date()
