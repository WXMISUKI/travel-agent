"""
时间上下文管理模块
负责维护会话级的时间上下文，确保日期解析的准确性
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from ..utils.logger import logger

# 中国时区
CHINA_TZ = timezone(timedelta(hours=8))


def get_china_now() -> datetime:
    """获取中国时区的当前时间"""
    return datetime.now(CHINA_TZ)


@dataclass
class TimeContext:
    """时间上下文"""
    current_time: datetime = field(default_factory=get_china_now)
    timezone: str = "Asia/Shanghai"
    
    def get_today(self) -> str:
        """获取今天日期"""
        return self.current_time.strftime("%Y-%m-%d")
    
    def get_today_formatted(self) -> str:
        """获取格式化的今天日期"""
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[self.current_time.weekday()]
        return f"{self.current_time.month}月{self.current_time.day}日 {weekday}"
    
    def get_relative_date(self, text: str) -> Optional[Dict[str, Any]]:
        """解析相对日期
        
        Args:
            text: 日期文本，如"明天"、"后天"、"下周一"等
            
        Returns:
            包含 parsed(日期), weekday(星期), original(原始文本) 的字典
        """
        text = text.strip()
        today = self.current_time
        today_weekday = today.weekday()
        weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekdays_short = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        result_date = None
        
        # 精确日期匹配
        date_patterns = {
            "今天": 0, "今日": 0,
            "明天": 1, "明日": 1,
            "后天": 2, "后日": 2,
            "大后天": 3, "大后日": 3,
            "大后天": 3,
            "昨天": -1, "昨日": -1,
            "前天": -2, "前日": -2,
        }
        
        if text in date_patterns:
            result_date = today + timedelta(days=date_patterns[text])
        
        # 周几匹配
        elif text in weekdays_short:
            target_weekday = weekdays_short.index(text)
            days_until = (target_weekday - today_weekday) % 7
            if days_until == 0:  # 如果是今天，默认下周
                days_until = 7
            result_date = today + timedelta(days=days_until)
        
        # "本周X" 模式
        elif text.startswith("本周") or text.startswith("这周"):
            day_text = text[2:]
            target_weekday = next((i for i, w in enumerate(weekdays_short) if w in day_text), None)
            if target_weekday is not None:
                days_until = (target_weekday - today_weekday) % 7
                result_date = today + timedelta(days=days_until)
        
        # "下周X" 模式
        elif text.startswith("下周"):
            day_text = text[2:]
            target_weekday = next((i for i, w in enumerate(weekdays_short) if w in day_text), None)
            if target_weekday is not None:
                days_until = (target_weekday - today_weekday) % 7
                if days_until == 0:
                    days_until = 7
                result_date = today + timedelta(days=7 + days_until)
        
        # 周末简写
        elif text in ["周末", "这个周末"]:
            # 距离最近的周六
            days_until_saturday = (5 - today_weekday) % 7
            if days_until_saturday == 0:  # 如果今天是周六，默认下周六
                days_until_saturday = 7
            result_date = today + timedelta(days=days_until_saturday)
        
        # 下周末
        elif text == "下周末":
            days_until_saturday = (5 - today_weekday) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7
            result_date = today + timedelta(days=7 + days_until_saturday)
        
        # 数字日期格式解析
        else:
            import re
            text_clean = text.replace("年", "-").replace("月", "-").replace("日", "").replace("号", "")
            
            # YYYY-MM-DD 格式
            match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text_clean)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                try:
                    result_date = datetime(year, month, day)
                except ValueError:
                    pass
            else:
                # MM-DD 格式
                match = re.search(r"(\d{1,2})-(\d{1,2})", text_clean)
                if match:
                    month, day = int(match.group(1)), int(match.group(2))
                    year = today.year
                    # 如果月份小于当前月份，认为是明年
                    if month < today.month:
                        year += 1
                    try:
                        result_date = datetime(year, month, day)
                    except ValueError:
                        pass
        
        if result_date is None:
            return None
        
        weekday_name = weekdays_cn[result_date.weekday()]
        
        return {
            "parsed": result_date.strftime("%Y-%m-%d"),
            "weekday": weekday_name,
            "original": text,
            "days_from_today": (result_date - today).days,
            "is_past": result_date < today,
            "is_today": result_date.date() == today.date()
        }
    
    def refresh(self):
        """刷新当前时间"""
        self.current_time = get_china_now()
        logger.info(f"时间上下文已刷新: {self.get_today_formatted()}")


# 全局时间上下文
_time_context: Optional[TimeContext] = None


def get_time_context() -> TimeContext:
    """获取全局时间上下文"""
    global _time_context
    if _time_context is None:
        _time_context = TimeContext()
        logger.info(f"时间上下文初始化: {_time_context.get_today_formatted()}")
    return _time_context


def parse_date_with_context(date_text: str) -> Dict[str, Any]:
    """使用上下文解析日期
    
    优先使用 LLM 解析，如果失败则使用规则解析
    """
    # 首先尝试规则解析
    context = get_time_context()
    result = context.get_relative_date(date_text)
    
    if result:
        # 验证解析结果是否合理
        if result["days_from_today"] < -7 or result["days_from_today"] > 365:
            logger.warning(f"日期解析结果超出合理范围: {result}")
            return {
                "original": date_text,
                "parsed": None,
                "error": f"日期超出合理范围"
            }
        return result
    
    # 规则解析失败，尝试 LLM 解析
    return {
        "original": date_text,
        "parsed": None,
        "error": f"无法解析日期: {date_text}"
    }
