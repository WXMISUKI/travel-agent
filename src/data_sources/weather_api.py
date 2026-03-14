"""
天气查询 API - 基于 apihz.cn 服务
支持省份+地点查询15天天气预报
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
    "http://101.35.2.25/api/tianqi/tqybmoji15.php",
    "http://124.222.204.22/api/tianqi/tqybmoji15.php",
    "http://81.68.149.132/api/tianqi/tqybmoji15.php"
]

# 获取最优接口的API
API_DISCOVERY_URL = "https://cn.apihz.cn/api/tianqi/tqybmoji15.php"

# 省份映射表
PROVINCE_MAP = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "台湾": "台湾省",
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区", "香港": "香港特别行政区", "澳门": "澳门特别行政区"
}


class WeatherAPI:
    """天气查询 API 客户端 - 15天预报版"""
    
    def __init__(self):
        self._cached_api = None
        self._cache_time = 0
        self._cache_ttl = 3600  # 缓存1小时
    
    def _get_province(self, city: str) -> str:
        """根据城市名获取省份"""
        # 清理城市名
        city = city.replace("市", "").replace("县", "").replace("区", "")
        
        # 直辖市
        if city in ["北京", "上海", "天津", "重庆"]:
            return f"{city}市"
        
        # 使用映射表
        for province, full_name in PROVINCE_MAP.items():
            if city.startswith(province) or province.startswith(city):
                return full_name
        
        # 常见城市默认省份
        default_provinces = {
            "杭州": "浙江省", "宁波": "浙江省", "温州": "浙江省", "嘉兴": "浙江省",
            "湖州": "浙江省", "绍兴": "浙江省", "金华": "浙江省", "衢州": "浙江省",
            "舟山": "浙江省", "台州": "浙江省", "丽水": "浙江省", "义乌": "浙江省",
            "南京": "江苏省", "苏州": "江苏省", "无锡": "江苏省", "常州": "江苏省",
            "徐州": "江苏省", "扬州": "江苏省", "镇江": "江苏省", "南通": "江苏省",
            "连云港": "江苏省", "淮安": "江苏省", "盐城": "江苏省", "泰州": "江苏省",
            "广州": "广东省", "深圳": "广东省", "东莞": "广东省", "佛山": "广东省",
            "珠海": "广东省", "中山": "广东省", "惠州": "广东省", "汕头": "广东省",
            "成都": "四川省", "绵阳": "四川省", "宜宾": "四川省", "泸州": "四川省",
            "武汉": "湖北省", "长沙": "湖南省", "岳阳": "湖南省", "株洲": "湖南省",
            "郑州": "河南省", "洛阳": "河南省", "开封": "河南省", "石家庄": "河北省",
            "保定": "河北省", "唐山": "河北省", "西安": "陕西省", "济南": "山东省",
            "青岛": "山东省", "烟台": "山东省", "威海": "山东省", "潍坊": "山东省",
            "厦门": "福建省", "福州": "福建省", "泉州": "福建省", "漳州": "福建省",
            "三明": "福建省", "莆田": "福建省", "宁德": "福建省", "南平": "福建省",
            "龙岩": "福建省",
            "南昌": "江西省", "赣州": "江西省", "九江": "江西省", "上饶": "江西省",
            "贵阳": "贵州省", "遵义": "贵州省", "昆明": "云南省", "大理": "云南省",
            "太原": "山西省", "合肥": "安徽省", "芜湖": "安徽省", "蚌埠": "安徽省",
            "哈尔滨": "黑龙江省", "长春": "吉林省", "沈阳": "辽宁省", "大连": "辽宁省",
            "呼和浩特": "内蒙古自治区", "南宁": "广西壮族自治区", "桂林": "广西壮族自治区",
            "海口": "海南省", "三亚": "海南省", "兰州": "甘肃省", "乌鲁木齐": "新疆维吾尔自治区",
            "银川": "宁夏回族自治区", "西宁": "青海省", "拉萨": "西藏自治区",
            "天津": "天津市",
        }
        
        return default_provinces.get(city, "北京市")
    
    async def _get_best_api(self) -> str:
        """获取最优 API 接口地址（带缓存）"""
        now = time.time()
        
        # 检查缓存
        if self._cached_api and (now - self._cache_time) < self._cache_ttl:
            return self._cached_api
        
        # 尝试获取最优接口
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{API_DISCOVERY_URL}?id={API_USER_ID}&key={API_KEY}&sheng=北京&place=北京"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        # 从URL中提取域名
                        api_url = str(resp.url) if resp.url else None
                        if api_url:
                            # 替换路径为正确的接口
                            if "/api/" in api_url:
                                base_url = api_url.split("/api/")[0]
                                api_url = f"{base_url}/api/tianqi/tqybmoji15.php"
                            self._cached_api = api_url
                            self._cache_time = now
                            logger.info(f"获取到天气接口: {api_url}")
                            return api_url
        except Exception as e:
            logger.warning(f"获取最优天气接口失败: {e}，使用备用接口")
        
        # 尝试备用接口
        for api in BACKUP_APIS:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{api}?id={API_USER_ID}&key={API_KEY}&sheng=北京&place=北京"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("code") in [200, 400]:
                                self._cached_api = api
                                self._cache_time = now
                                logger.info(f"使用备用天气接口: {api}")
                                return api
            except:
                continue
        
        # 如果都失败，使用默认
        self._cached_api = BACKUP_APIS[0]
        return self._cached_api
    
    async def query_weather(self, city: str) -> Dict[str, Any]:
        """
        查询天气预报
        
        Args:
            city: 城市名称（如"北京"、"上海"、"杭州"）
        
        Returns:
            标准化的天气数据
        """
        # 获取省份
        province = self._get_province(city)
        
        # 提取城市名（去掉市、县等后缀）
        city_clean = city.replace("市", "").replace("县", "").replace("区", "")
        
        # 获取最优接口
        api_url = await self._get_best_api()
        
        try:
            # 构建请求
            url = f"{api_url}?id={API_USER_ID}&key={API_KEY}&sheng={province}&place={city_clean}"
            
            logger.info(f"请求天气API: {url[:100]}...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return {
                            "error": f"HTTP {resp.status}",
                            "city": city
                        }
                    
                    data = await resp.json()
                    return self._parse_response(data, city, province)
                    
        except asyncio.TimeoutError:
            logger.error("天气API请求超时")
            return {
                "error": "请求超时",
                "city": city
            }
        except Exception as e:
            logger.error(f"天气API请求失败: {e}")
            return {
                "error": str(e),
                "city": city
            }
    
    def _parse_response(self, data: Dict, city: str, province: str) -> Dict:
        """解析API响应"""
        
        if data.get("code") != 200:
            error_msg = data.get("msg", "未知错误")
            return {
                "error": error_msg,
                "city": city,
                "weather": {}
            }
        
        # 解析天气数据
        weather_data = data.get("data", [])
        
        if not weather_data:
            return {
                "error": "无天气数据",
                "city": city,
                "weather": {}
            }
        
        result = {
            "success": True,
            "city": city,
            "province": province,
            "location": data.get("place", ""),
            "forecast": [],
            "today": None
        }
        
        # 解析预报数据
        for i, day in enumerate(weather_data[:7]):  # 只取7天
            forecast_day = {
                "week": day.get("week1", ""),
                "date": day.get("week2", ""),
                "weather_day": day.get("wea1", ""),
                "weather_night": day.get("wea2", ""),
                "temp_high": day.get("wendu1", ""),
                "temp_low": day.get("wendu2", ""),
                "icon_day": day.get("img1", ""),
                "icon_night": day.get("img2", "")
            }
            result["forecast"].append(forecast_day)
            
            # 今天的数据
            if i == 0:
                result["today"] = forecast_day
        
        return result


# 全局实例
_weather_api = None


def get_weather_api() -> WeatherAPI:
    """获取天气API实例"""
    global _weather_api
    if _weather_api is None:
        _weather_api = WeatherAPI()
    return _weather_api