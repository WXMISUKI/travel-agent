"""
火车票API测试脚本
测试 apihz.cn 火车票接口是否可用
"""
import asyncio
import aiohttp
import json

# API配置
API_USER_ID = "10013949"
API_KEY = "9c8a62dfe79ed9bb426a16926f019509"

# 备用接口列表
API_LIST = [
    "http://101.35.2.25/api/12306/api4.php",
    "http://124.222.204.22/api/12306/api4.php",
    "http://81.68.149.132/api/12306/api4.php",
    "https://cn.apihz.cn/api/12306/api4.php"
]


async def test_train_api(api_url: str, from_station: str, to_station: str, 
                        year: str, month: str, day: str) -> dict:
    """测试单个火车票API"""
    try:
        url = f"{api_url}?id={API_USER_ID}&key={API_KEY}&add={from_station}&end={to_station}&y={year}&m={month}&d={day}"
        print(f"\n测试URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                status = resp.status
                text = await resp.text()
                print(f"状态码: {status}")
                print(f"响应内容: {text[:800]}")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        return {
                            "api": api_url,
                            "success": data.get("code") == 200,
                            "data": data
                        }
                    except:
                        return {
                            "api": api_url,
                            "success": False,
                            "error": "JSON解析失败"
                        }
                else:
                    return {
                        "api": api_url,
                        "success": False,
                        "error": f"HTTP {status}"
                    }
    except asyncio.TimeoutError:
        return {
            "api": api_url,
            "success": False,
            "error": "请求超时"
        }
    except Exception as e:
        return {
            "api": api_url,
            "success": False,
            "error": str(e)
        }


async def test_all_apis():
    """测试所有火车票API"""
    # 测试用例：明天(2026-03-15) 从三明北到宁波
    test_cases = [
        ("三明北", "宁波", "2026", "03", "15"),
        ("北京", "上海", "2026", "03", "15"),
        ("杭州", "南京", "2026", "03", "15"),
    ]
    
    for from_station, to_station, year, month, day in test_cases:
        print(f"\n{'='*60}")
        print(f"测试: {from_station} -> {to_station}, 日期: {year}-{month}-{day}")
        print('='*60)
        
        for api_url in API_LIST:
            result = await test_train_api(api_url, from_station, to_station, year, month, day)
            if result["success"]:
                print(f"✅ API可用: {api_url}")
                data = result["data"]
                print(f"返回数据: {json.dumps(data, ensure_ascii=False)[:500]}")
                break
            else:
                print(f"❌ API失败: {api_url}")
                print(f"错误: {result.get('error')}")


if __name__ == "__main__":
    print("火车票API测试开始...")
    asyncio.run(test_all_apis())
