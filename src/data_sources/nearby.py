"""
周边景点/POI查询API - 使用 apihz.cn 接口
功能：
1. 地址转经纬度 (jwjuhe.php)
2. 经纬度周边地点查询 (diming.php)
"""
import json
import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 开发者配置
API_ID = "10013949"
API_KEY = "9c8a62dfe79ed9bb426a16926f019509"

# 备用接口列表
GEOCODE_API_LIST = [
    "http://101.35.2.25/api/other/jwjuhe.php",
    "http://124.222.204.22/api/other/jwjuhe.php",
    "http://81.68.149.132/api/other/jwjuhe.php",
]

POI_API_LIST = [
    "http://101.35.2.25/api/other/diming.php",
    "http://124.222.204.22/api/other/diming.php",
    "http://81.68.149.132/api/other/diming.php",
]

# 缓存
_geo_cache: Dict[str, Dict] = {}


def get_geocode(address: str) -> Optional[Dict]:
    """获取地址的经纬度
    
    Args:
        address: 地址（如"杭州市"、"西湖"）
    
    Returns:
        {"lng": "经度", "lat": "纬度"} 或 None
    """
    global _geo_cache
    
    # 检查缓存
    if address in _geo_cache:
        return _geo_cache[address]
    
    for api_url in GEOCODE_API_LIST:
        try:
            params = {
                "id": API_ID,
                "key": API_KEY,
                "address": address
            }
            
            resp = requests.get(api_url, params=params, timeout=10)
            data = resp.json()
            
            if data.get("code") == 200:
                result = {
                    "lng": data.get("lng", ""),
                    "lat": data.get("lat", ""),
                    "score": data.get("score", 0),
                    "level": data.get("level", "")
                }
                _geo_cache[address] = result
                logger.info(f"获取经纬度成功: {address} -> {result}")
                return result
            else:
                logger.warning(f"获取经纬度失败: {address}, {data.get('msg')}")
                
        except Exception as e:
            logger.warning(f"请求经纬度接口失败: {e}")
            continue
    
    return None


def search_nearby(
    words: str,
    lon: float,
    lat: float,
    radius: int = 3000,
    page: int = 1
) -> Dict:
    """查询周边地点
    
    Args:
        words: 关键词（景点、美食、酒店等）
        lon: 经度
        lat: 纬度
        radius: 半径（米），默认3公里
        page: 页码
    
    Returns:
        周边地点列表
    """
    for api_url in POI_API_LIST:
        try:
            params = {
                "id": API_ID,
                "key": API_KEY,
                "words": words,
                "lon": str(lon),
                "lat": str(lat),
                "radius": str(radius),
                "page": str(page),
                "show": "1"
            }
            
            resp = requests.get(api_url, params=params, timeout=10)
            data = resp.json()
            
            if data.get("code") == 200:
                return data
            else:
                logger.warning(f"查询周边地点失败: {data.get('msg')}")
                
        except Exception as e:
            logger.warning(f"请求周边地点接口失败: {e}")
            continue
    
    return {"code": 400, "msg": "查询失败"}


def query_attractions(city: str, keyword: str = "景点", radius: int = 5000) -> Dict:
    """查询城市周边景点
    
    Args:
        city: 城市名
        keyword: 关键词（默认"景点"）
        radius: 查询半径（米）
    
    Returns:
        标准化的景点列表
    """
    # 1. 获取城市经纬度
    geo = get_geocode(city)
    
    if not geo:
        return {
            "success": False,
            "city": city,
            "error": f"无法获取{city}的坐标"
        }
    
    # 2. 查询周边景点
    result = search_nearby(
        words=keyword,
        lon=float(geo["lng"]),
        lat=float(geo["lat"]),
        radius=radius
    )
    
    if result.get("code") != 200:
        return {
            "success": False,
            "city": city,
            "error": result.get("msg", "查询失败")
        }
    
    # 3. 解析结果
    attractions = []
    for item in result.get("datas", [])[:10]:  # 最多返回10个
        attractions.append({
            "name": item.get("name", ""),
            "address": item.get("address", ""),
            "distance": item.get("distance", ""),
            "type": item.get("typeName", keyword),
            "county": item.get("county", "")
        })
    
    return {
        "success": True,
        "city": city,
        "keyword": keyword,
        "location": {
            "lng": geo["lng"],
            "lat": geo["lat"]
        },
        "count": len(attractions),
        "attractions": attractions
    }


# 导出
__all__ = ["get_geocode", "search_nearby", "query_attractions"]
