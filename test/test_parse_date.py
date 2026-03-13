"""
日期解析工具测试
"""
import json
import re
from datetime import datetime, timedelta


def parse_date(date_text: str) -> str:
    """解析自然语言日期"""
    
    today = datetime.now()
    today_weekday = today.weekday()  # 0=周一, 6=周日
    weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekdays_short = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekdays_full = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    text = date_text.strip()
    result_date = None
    
    # 1. 处理"今天"
    if text in ["今天", "今日"]:
        result_date = today
    
    # 2. 处理"明天"、"后天"、"大后天"
    elif text in ["明天", "明日"]:
        result_date = today + timedelta(days=1)
    elif text in ["后天", "后日"]:
        result_date = today + timedelta(days=2)
    elif text in ["大后天", "大后日"]:
        result_date = today + timedelta(days=3)
    
    # 3. 处理"昨天"、"前天"
    elif text in ["昨天", "昨日"]:
        result_date = today - timedelta(days=1)
    elif text in ["前天", "前日"]:
        result_date = today - timedelta(days=2)
    elif text in ["大前天", "大前日"]:
        result_date = today - timedelta(days=3)
    
    # 4. 处理"下周X"
    elif text.startswith("下周"):
        day_text = date_text[2:]
        target_weekday = None
        for i, w in enumerate(weekdays_short):
            if w in day_text or w in date_text[2:]:
                target_weekday = i
                break
        if target_weekday is None:
            for i, w in enumerate(weekdays_short):
                if w[1] in day_text:
                    target_weekday = i
                    break
        
        if target_weekday is not None:
            days_until_target = (target_weekday - today_weekday) % 7
            if days_until_target == 0:
                days_until_target = 7
            result_date = today + timedelta(days=7 + days_until_target)
    
    # 5. 处理"本周X"
    elif text.startswith("本周") or text.startswith("这周"):
        day_text = date_text[2:] if text.startswith("本") else date_text[2:]
        target_weekday = None
        for i, w in enumerate(weekdays_short):
            if w in day_text or w in date_text[2:]:
                target_weekday = i
                break
        if target_weekday is None:
            for i, w in enumerate(weekdays_short):
                if w[1] in day_text:
                    target_weekday = i
                    break
        
        if target_weekday is not None:
            days_until_target = (target_weekday - today_weekday) % 7
            result_date = today + timedelta(days=days_until_target)
    
    # 6. 处理单独的周几
    elif text in weekdays_short or text in weekdays_full or text in weekdays_cn:
        for i, w in enumerate(weekdays_short):
            if text == w or text == weekdays_full[i] or text == weekdays_cn[i]:
                target_weekday = i
                break
        
        if target_weekday is not None:
            days_until_target = (target_weekday - today_weekday) % 7
            if days_until_target == 0:
                days_until_target = 7
            result_date = today + timedelta(days=days_until_target)
    
    # 7. 处理具体日期格式
    else:
        text_clean = text.replace("年", "-").replace("月", "-").replace("日", "").replace("号", "")
        date_patterns = [
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
            r"(\d{1,2})-(\d{1,2})",
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text_clean)
            if match:
                if len(match.groups()) == 3:
                    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    result_date = datetime(year, month, day)
                else:
                    month, day = int(match.group(1)), int(match.group(2))
                    year = today.year
                    if month < today.month:
                        year += 1
                    result_date = datetime(year, month, day)
                break
    
    if result_date is None:
        return json.dumps({
            "original": date_text,
            "parsed": None,
            "error": f"无法解析日期: {date_text}"
        }, ensure_ascii=False)
    
    weekday_name = weekdays_cn[result_date.weekday()]
    return json.dumps({
        "original": date_text,
        "parsed": result_date.strftime("%Y-%m-%d"),
        "weekday": weekday_name,
        "description": f"{result_date.strftime('%Y-%m-%d')} ({weekday_name})"
    }, ensure_ascii=False, indent=2)


def test_parse_date():
    """测试日期解析功能"""
    
    test_cases = [
        # 相对日期
        ("明天", "相对日期-明天"),
        ("后天", "相对日期-后天"),
        ("大后天", "相对日期-大后天"),
        ("昨天", "相对日期-昨天"),
        
        # 周几
        ("今天", "今天"),
        ("周一", "周一"),
        ("周五", "周五"),
        
        # 本周
        ("本周六", "本周六"),
        ("这周日", "这周日"),
        
        # 下周
        ("下周一", "下周一"),
        ("下周五", "下周五"),
        
        # 具体日期
        ("3月15日", "3月15日"),
        ("03-20", "03-20"),
        ("2026-03-20", "2026-03-20"),
    ]
    
    print("=" * 60)
    print("日期解析工具测试")
    print(f"当前日期: {datetime.now().strftime('%Y-%m-%d %A')}")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for date_text, description in test_cases:
        print(f"\n测试: {description} ({date_text})")
        try:
            result = parse_date(date_text)
            print(f"结果: {result}")
            
            data = json.loads(result)
            if data.get("parsed"):
                print(f"✅ 通过 - 解析为: {data['parsed']} ({data.get('weekday', '')})")
                passed += 1
            else:
                print(f"❌ 失败 - 错误: {data.get('error', '未知错误')}")
                failed += 1
        except Exception as e:
            print(f"❌ 异常: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)


if __name__ == "__main__":
    test_parse_date()