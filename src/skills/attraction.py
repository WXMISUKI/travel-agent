"""
景点查询 Skill
"""
from typing import Dict
from .base import BaseSkill, SkillInput, SkillOutput
from ..data_sources.baidu_search import BaiduSearchAPI


class AttractionSkill(BaseSkill):
    """景点查询 Skill"""
    
    name = "attraction"
    description = "搜索景点、美食、当地推荐"
    
    def __init__(self):
        self.baidu_search = BaiduSearchAPI()
    
    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """执行景点查询"""
        try:
            params = input_data.get("query_params", {})
            city = params.get("city")
            keyword = params.get("keyword", "景点")
            
            if not city:
                return self._create_error_output("缺少城市参数")
            
            # 调用百度搜索
            data = await self.baidu_search.search(city, keyword)
            
            return self._create_success_output(data)
            
        except Exception as e:
            return self._create_error_output(f"景点查询失败: {str(e)}")
    
    async def search_multiple(self, city: str, keywords: list) -> Dict:
        """批量搜索多个关键词"""
        try:
            return await self.baidu_search.search_multiple(city, keywords)
        except Exception as e:
            return {"error": str(e)}
    
    async def search_sync(self, city: str, keyword: str = "景点") -> Dict:
        """同步搜索（供Tool调用）"""
        try:
            return await self.baidu_search.search(city, keyword)
        except Exception as e:
            return {"error": str(e)}
