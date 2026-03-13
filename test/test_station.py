"""
火车站查询工具测试 - 模拟测试
"""
import json
import re


def parse_stations_from_text(text: str) -> list:
    """从文本中提取火车站名"""
    stations = []
    station_names = set()
    
    # 匹配 "XXX站" 模式
    matches = re.findall(r'([^\s,，、]+站)', text)
    for match in matches:
        if len(match) >= 3:  # 站名至少3个字符
            station_names.add(match)
    
    # 构建火车站列表
    for name in list(station_names)[:10]:
        station_type = "火车站"
        if "高铁" in name or "东站" in name or "南站" in name:
            station_type = "高铁站"
        stations.append({"name": name, "type": station_type})
    
    return stations


def test_station_parsing():
    """测试火车站解析功能"""
    
    # 模拟搜索结果文本
    test_cases = [
        {
            "text": """
            沙县附近火车站有：三明北站（高铁站）、三明站、永安南站、尤溪站等。
            其中三明北站是距离沙县最近的高铁站，每天有多个班次往返福州、厦门等地。
            """,
            "expected_stations": ["三明北站", "三明站", "永安南站", "尤溪站"]
        },
        {
            "text": """
            嘉兴附近火车站：嘉兴站、嘉兴南站（高铁站）、海宁站、桐乡站等。
            嘉兴南站是沪杭高铁的重要站点，交通便利。
            """,
            "expected_stations": ["嘉兴站", "嘉兴南站", "海宁站", "桐乡站"]
        },
        {
            "text": """
            宁波火车站列表：宁波站、宁波东站、余姚站、奉化站等。
            宁波站是主要的高铁站，宁波东站也有动车停靠。
            """,
            "expected_stations": ["宁波站", "宁波东站", "余姚站", "奉化站"]
        }
    ]
    
    print("=" * 60)
    print("火车站查询工具测试")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试案例 {i}:")
        print(f"文本: {case['text'][:100]}...")
        
        stations = parse_stations_from_text(case["text"])
        
        print(f"\n提取到的火车站:")
        for s in stations:
            print(f"  - {s['name']} ({s['type']})")
        
        # 验证
        found_names = [s['name'] for s in stations]
        expected_found = [e for e in case['expected_stations'] if e in found_names]
        
        if len(expected_found) >= len(case['expected_stations']) * 0.5:  # 至少匹配一半
            print(f"✅ 通过 - 匹配到 {len(expected_found)}/{len(case['expected_stations'])} 个火车站")
            passed += 1
        else:
            print(f"❌ 失败 - 只匹配到 {len(expected_found)}/{len(case['expected_stations'])} 个火车站")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)


if __name__ == "__main__":
    test_station_parsing()
