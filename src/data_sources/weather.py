"""
Open-Meteo 天气API - 开源免费
"""
import aiohttp
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# 城市经纬度映射（常见城市）
CITY_COORDS = {
    "北京": {"lat": 39.90, "lon": 116.41},
    "上海": {"lat": 31.23, "lon": 121.47},
    "广州": {"lat": 23.13, "lon": 113.26},
    "深圳": {"lat": 22.54, "lon": 114.06},
    "成都": {"lat": 30.67, "lon": 104.07},
    "杭州": {"lat": 30.27, "lon": 120.15},
    "西安": {"lat": 34.34, "lon": 108.94},
    "重庆": {"lat": 29.56, "lon": 106.55},
    "南京": {"lat": 32.06, "lon": 118.79},
    "武汉": {"lat": 30.59, "lon": 114.31},
    "天津": {"lat": 39.13, "lon": 117.20},
    "苏州": {"lat": 31.30, "lon": 120.58},
    "郑州": {"lat": 34.76, "lon": 113.75},
    "长沙": {"lat": 28.23, "lon": 112.94},
    "青岛": {"lat": 36.07, "lon": 120.38},
    "沈阳": {"lat": 41.81, "lon": 123.43},
    "大连": {"lat": 38.92, "lon": 121.63},
    "厦门": {"lat": 24.48, "lon": 118.09},
    "昆明": {"lat": 25.04, "lon": 102.71},
    "哈尔滨": {"lat": 45.80, "lon": 126.53},
    "长春": {"lat": 43.88, "lon": 125.32},
    "福州": {"lat": 26.08, "lon": 119.30},
    "南昌": {"lat": 28.68, "lon": 115.86},
    "贵阳": {"lat": 26.65, "lon": 106.63},
    "太原": {"lat": 37.87, "lon": 112.55},
    "济南": {"lat": 36.65, "lon": 117.12},
    "南宁": {"lat": 22.82, "lon": 108.37},
    "合肥": {"lat": 31.82, "lon": 117.23},
    "石家庄": {"lat": 38.04, "lon": 114.51},
    "兰州": {"lat": 36.06, "lon": 103.75},
    "乌鲁木齐": {"lat": 43.83, "lon": 87.62},
    "银川": {"lat": 38.47, "lon": 106.23},
    "西宁": {"lat": 36.62, "lon": 101.78},
    "拉萨": {"lat": 29.65, "lon": 91.10},
    "呼和浩特": {"lat": 40.84, "lon": 111.75},
    "海口": {"lat": 20.04, "lon": 110.35},
    "三亚": {"lat": 18.25, "lon": 109.51},
    "东莞": {"lat": 23.04, "lon": 113.75},
    "佛山": {"lat": 23.02, "lon": 113.12},
    "宁波": {"lat": 29.87, "lon": 121.55},
    "温州": {"lat": 28.00, "lon": 120.69},
    "无锡": {"lat": 31.49, "lon": 120.30},
    "常州": {"lat": 31.81, "lon": 119.97},
    "徐州": {"lat": 34.20, "lon": 117.29},
    "扬州": {"lat": 32.39, "lon": 119.43},
    "镇江": {"lat": 32.20, "lon": 119.45},
    "绍兴": {"lat": 30.00, "lon": 120.58},
    "嘉兴": {"lat": 30.75, "lon": 120.76},
    "湖州": {"lat": 30.87, "lon": 120.09},
    "金华": {"lat": 29.08, "lon": 119.65},
    "台州": {"lat": 28.65, "lon": 121.43},
    "丽水": {"lat": 28.46, "lon": 119.92},
    "舟山": {"lat": 29.98, "lon": 122.11},
    "衢州": {"lat": 28.97, "lon": 118.87},
    "芜湖": {"lat": 31.33, "lon": 118.38},
    "蚌埠": {"lat": 32.92, "lon": 117.39},
    "淮南": {"lat": 32.63, "lon": 117.00},
    "马鞍山": {"lat": 31.67, "lon": 118.51},
    "安庆": {"lat": 30.54, "lon": 117.05},
    "宿州": {"lat": 33.65, "lon": 116.96},
    "阜阳": {"lat": 32.89, "lon": 115.81},
    "黄山": {"lat": 29.72, "lon": 118.34},
    "滁州": {"lat": 32.30, "lon": 118.32},
    "池州": {"lat": 30.66, "lon": 117.49},
    "宣城": {"lat": 30.94, "lon": 118.87},
}


class OpenMeteoAPI:
    """Open-Meteo 天气API 客户端"""
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    # 天气代码映射
    WEATHER_CODES = {
        0: "晴",
        1: "晴间多云", 2: "多云", 3: "阴",
        45: "雾", 48: "霜雾",
        51: "小毛毛雨", 53: "中雨", 55: "大雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        80: "阵雨", 81: "阵雨", 82: "强阵雨",
        95: "雷暴", 96: "雷暴", 99: "雷暴"
    }
    
    async def get_weather(self, city: str) -> Dict:
        """获取城市天气"""
        
        # 查找城市坐标
        coords = CITY_COORDS.get(city)
        if not coords:
            raise ValueError(f"暂不支持查询城市: {city}，请尝试其他城市")
        
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "current_weather": "true",
            "hourly": "temperature_2m,precipitation_probability,weathercode",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
            "timezone": "Asia/Shanghai",
            "forecast_days": 7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.BASE_URL, params=params) as resp:
                if resp.status != 200:
                    raise Exception(f"天气API调用失败: {resp.status}")
                
                data = await resp.json()
                return self._parse_weather(data, city)
    
    def _parse_weather(self, data: Dict, city: str) -> Dict:
        """解析天气数据"""
        
        current = data.get("current_weather", {})
        daily = data.get("daily", {})
        
        result = {
            "城市": city,
            "当前天气": {
                "温度": f"{current.get('temperature', 'N/A')}°C",
                "天气": self.WEATHER_CODES.get(current.get('weathercode'), "未知"),
                "风速": f"{current.get('windspeed', 'N/A')} km/h",
                "风向": self._get_wind_direction(current.get('winddirection', 0))
            },
            "未来几天": []
        }
        
        # 解析未来几天预报
        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        weather_codes = daily.get("weathercode", [])
        
        for i, date in enumerate(dates):
            result["未来几天"].append({
                "日期": date,
                "最高温": f"{max_temps[i]}°C" if i < len(max_temps) else "N/A",
                "最低温": f"{min_temps[i]}°C" if i < len(min_temps) else "N/A",
                "降水量": f"{precip[i]}mm" if i < len(precip) else "N/A",
                "天气": self.WEATHER_CODES.get(weather_codes[i], "未知") if i < len(weather_codes) else "未知"
            })
        
        return result
    
    def _get_wind_direction(self, degrees: float) -> str:
        """风速方向转换"""
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        index = int((degrees + 22.5) // 45) % 8
        return directions[index]
