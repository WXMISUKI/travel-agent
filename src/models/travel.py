"""
旅行相关数据模型
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class TravelQuery:
    """旅行查询参数"""
    destination: str = ""          # 目的地
    origin: str = ""               # 出发地
    date: str = ""                 # 出发日期
    days: int = 0                  # 旅行天数
    budget: str = ""               # 预算
    preferences: List[str] = field(default_factory=list)  # 偏好


@dataclass
class WeatherInfo:
    """天气信息"""
    city: str
    temperature: str
    weather: str
    wind: str
    forecast: List[Dict] = field(default_factory=list)


@dataclass
class TicketInfo:
    """车票信息"""
    train_no: str
    from_station: str
    to_station: str
    depart_time: str
    arrive_time: str
    duration: str
    price: str
    remaining: str


@dataclass
class AttractionInfo:
    """景点信息"""
    name: str
    description: str
    rating: Optional[str] = None
    address: str = ""
    opening_hours: str = ""
    ticket_price: str = ""


@dataclass
class TravelPlan:
    """旅行计划"""
    destination: str
    days: int
    daily_plan: List[Dict] = field(default_factory=list)
    transportation: Dict = field(default_factory=dict)
    tips: List[str] = field(default_factory=list)
    estimated_budget: str = ""
