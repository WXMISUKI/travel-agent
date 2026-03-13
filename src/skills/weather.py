"""
天气查询 Skill
"""
from typing import Dict
from .base import BaseSkill, SkillInput, SkillOutput
from ..data_sources.weather import OpenMeteoAPI


class WeatherSkill(BaseSkill):
    """天气查询 Skill"""
    
    name = "weather"
    description = "查询目的地天气"
    
    def __init__(self):
        self.weather_api = OpenMeteoAPI()
    
    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """执行天气查询"""
        try:
            params = input_data.get("query_params", {})
            city = params.get("city")
            
            if not city:
                return self._create_error_output("缺少城市参数")
            
            # 调用天气API
            data = await self.weather_api.get_weather(city)
            
            return self._create_success_output(data)
            
        except ValueError as e:
            return self._create_error_output(str(e))
        except Exception as e:
            return self._create_error_output(f"天气查询失败: {str(e)}")
    
    async def get_weather_sync(self, city: str) -> Dict:
        """同步获取天气（供Tool调用）"""
        try:
            return await self.weather_api.get_weather(city)
        except Exception as e:
            return {"error": str(e)}
