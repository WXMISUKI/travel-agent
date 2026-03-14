"""
天气API测试脚本
测试 apihz.cn 天气接口是否可用
"""
import asyncio
import aiohttp
import json

# API配置
API_USER_ID = "10013949"
API_KEY = "9c8a62dfe79ed9bb426a16926f019509"

# 备用接口列表
API_LIST = [
    "http://101.35.2.25/api/tianqi/tqybmoji15.php",
    "http://124.222.204.22/api/tianqi/tqybmoji15.php",
    "http://81.68.149.132/api/tianqi/tqybmoji15.php",
    "https://cn.apihz.cn/api/tianqi/tqybmoji15.php"
]


async def test_weather_api(api_url: str, province: str, city: str) -> dict:
    """测试单个天气API"""
    try:
        url = f"{api_url}?id={API_USER_ID}&key={API_KEY}&sheng={province}&place={city}"
        print(f"\n测试URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                status = resp.status
                text = await resp.text()
                print(f"状态码: {status}")
                print(f"响应内容: {text[:500]}")
                
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
    """测试所有天气API"""
    # 测试城市
    test_cases = [
        ("北京", "北京市", "北京"),
        ("浙江", "浙江省", "杭州"),
        ("福建", "福建省", "福州"),
        ("上海", "上海市", "上海"),
    ]
    
    for province, full_province, city in test_cases:
        print(f"\n{'='*60}")
        print(f"测试城市: {city} ({full_province})")
        print('='*60)
        
        for api_url in API_LIST:
            result = await test_weather_api(api_url, full_province, city)
            if result["success"]:
                print(f"✅ API可用: {api_url}")
                print(f"数据: {json.dumps(result['data'], ensure_ascii=False)[:200]}")
                break
            else:
                print(f"❌ API失败: {api_url}")
                print(f"错误: {result.get('error')}")


async def test_specific_city(province: str, city: str):
    """测试指定城市"""
    print(f"\n{'='*60}")
    print(f"测试城市: {city} ({province})")
    print('='*60)
    
    for api_url in API_LIST:
        result = await test_weather_api(api_url, province, city)
        if result["success"]:
            print(f"✅ API可用: {api_url}")
            data = result["data"]
            if data.get("code") == 200:
                print("✅ 返回成功!")
                print(f"地点: {data.get('place')}")
                print(f"数据: {json.dumps(data.get('data', [])[:3], ensure_ascii=False, indent=2)}")
            else:
                print(f"❌ API返回错误: {data.get('msg')}")
            break
        else:
            print(f"❌ API失败: {result.get('error')}")


if __name__ == "__main__":
    print("天气API测试开始...")
    asyncio.run(test_all_apis())
