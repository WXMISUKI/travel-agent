"""
百度搜索API - 通用搜索版
"""
import aiohttp
import os
import json
import logging
from typing import Dict, List
from ..config import BAIDU_SEARCH_API_KEY

logger = logging.getLogger(__name__)


class BaiduSearchAPI:
    """百度搜索API 客户端"""
    
    BASE_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    
    def __init__(self):
        self.api_key = BAIDU_SEARCH_API_KEY
    
    async def search(self, city: str, keyword: str = "景点") -> Dict:
        """搜索景点/美食"""
        query = f"{city} {keyword}"
        return await self._do_search(query)
    
    async def search_generic(self, query: str) -> Dict:
        """通用搜索"""
        return await self._do_search(query)
    
    async def search_weather(self, city: str) -> Dict:
        """搜索天气"""
        query = f"{city} 天气预报"
        return await self._do_search(query)
    
    async def search_transport(self, from_city: str, to_city: str) -> Dict:
        """搜索交通方案"""
        query = f"{from_city} 到 {to_city} 交通方式"
        return await self._do_search(query)
    
    async def search_stations(self, city: str) -> Dict:
        """搜索城市附近的火车站"""
        query = f"{city} 附近火车站"
        return await self._do_search(query)
    
    async def _do_search(self, query: str) -> Dict:
        """执行搜索"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "content": query,
                    "role": "user"
                }
            ],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [
                {"type": "web", "top_k": 10}
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.BASE_URL, 
                    json=payload, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"百度搜索失败: {resp.status}, {text}")
                        return {"error": f"HTTP {resp.status}", "results": []}
                    
                    data = await resp.json()
                    
                    if "code" in data and data["code"]:
                        logger.error(f"百度搜索API错误: {data.get('message')}")
                        return {"error": data.get("message", "API错误"), "results": []}
                    
                    return self._parse_results(data)
        
        except Exception as e:
            logger.error(f"百度搜索异常: {e}")
            return {"error": str(e), "results": []}
    
    def _parse_results(self, data: Dict) -> Dict:
        """解析搜索结果"""
        
        references = data.get("references", [])
        if not references:
            return {"results": [], "error": "未找到相关结果"}
        
        parsed = []
        for item in references:
            parsed.append({
                "标题": item.get("title", ""),
                "摘要": item.get("content", "")[:200],
                "链接": item.get("url", ""),
                "网站": item.get("website", ""),
                "日期": item.get("date", "")
            })
        
        return {
            "results": parsed,
            "count": len(parsed)
        }
    
    async def search_multiple(self, city: str, keywords: List[str]) -> Dict:
        """批量搜索"""
        all_results = {}
        for keyword in keywords:
            result = await self.search(city, keyword)
            all_results[keyword] = result
        return all_results
