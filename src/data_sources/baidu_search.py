"""
百度搜索API - Fallback方案
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
        """执行搜索"""
        
        query = f"{city} {keyword}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": 10
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
                        logger.warning(f"百度搜索失败: {resp.status}")
                        return self._create_fallback_result(query)
                    
                    data = await resp.json()
                    return self._parse_search_results(data, city, keyword)
        
        except aiohttp.ClientError as e:
            logger.error(f"百度搜索异常: {e}")
            return self._create_fallback_result(query)
        except Exception as e:
            logger.error(f"百度搜索未知异常: {e}")
            return self._create_fallback_result(query)
    
    def _create_fallback_result(self, query: str) -> Dict:
        """创建降级结果"""
        return {
            "城市": query.split()[0] if query else "",
            "关键词": query.split()[1] if len(query.split()) > 1 else "景点",
            "results": [],
            "error": "搜索服务暂时不可用，请稍后重试"
        }
    
    def _parse_search_results(self, data: Dict, city: str, keyword: str) -> Dict:
        """解析搜索结果"""
        
        results = data.get("results", [])
        if not results:
            return {
                "城市": city,
                "关键词": keyword,
                "results": [],
                "error": "未找到相关结果"
            }
        
        parsed = []
        for item in results:
            parsed.append({
                "标题": item.get("title", "").replace("<em>", "").replace("</em>", ""),
                "摘要": item.get("snippet", "").replace("<em>", "").replace("</em>", ""),
                "链接": item.get("url", "")
            })
        
        return {
            "城市": city,
            "关键词": keyword,
            "results": parsed,
            "count": len(parsed)
        }
    
    async def search_multiple(self, city: str, keywords: List[str]) -> Dict:
        """批量搜索多个关键词"""
        all_results = {}
        
        for keyword in keywords:
            result = await self.search(city, keyword)
            all_results[keyword] = result
        
        return all_results
