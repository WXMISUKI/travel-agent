"""
缓存工具
"""
from functools import lru_cache
import hashlib
import json
import time
from typing import Any, Optional


class QueryCache:
    """查询结果缓存"""
    
    def __init__(self, ttl: int = 3600):
        self._cache = {}
        self._ttl = ttl
    
    def _make_key(self, query: str, params: dict) -> str:
        """生成缓存key"""
        data = json.dumps({"query": query, "params": params}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, query: str, params: dict = None) -> Optional[Any]:
        """获取缓存"""
        params = params or {}
        key = self._make_key(query, params)
        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return result
            else:
                del self._cache[key]
        return None
    
    def set(self, query: str, value: Any, params: dict = None):
        """设置缓存"""
        params = params or {}
        key = self._make_key(query, params)
        self._cache[key] = (value, time.time())
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()


# 全局缓存实例
query_cache = QueryCache()
