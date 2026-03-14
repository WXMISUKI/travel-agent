"""
LangGraph 工作流状态定义
基于 Pydantic 的结构化状态管理
"""
from typing import TypedDict, Annotated, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class IntentType(str, Enum):
    """意图类型枚举"""
    TRAIN_TICKETS = "train_tickets"
    WEATHER = "weather"
    ATTRACTIONS = "attractions"
    TRANSPORT = "transport"
    HOTEL = "hotel"
    GENERAL = "general"
    UNKNOWN = "unknown"


class ExtractedEntities(BaseModel):
    """提取的实体模型"""
    origin: Optional[str] = Field(None, description="出发地城市")
    destination: Optional[str] = Field(None, description="目的地城市")
    date_text: Optional[str] = Field(None, description="原始日期文本")
    parsed_date: Optional[str] = Field(None, description="解析后的日期 YYYY-MM-DD")
    weekday: Optional[str] = Field(None, description="星期几")
    train_type: Optional[str] = Field(None, description="火车类型 G/D/K")
    keyword: Optional[str] = Field(None, description="搜索关键词")


class ToolParams(BaseModel):
    """工具参数模型"""
    from_station: Optional[str] = None
    to_station: Optional[str] = None
    date: Optional[str] = None
    train_type: str = "G"
    city: Optional[str] = None
    keyword: str = "景点"
    query: Optional[str] = None


class ExecutionStep(BaseModel):
    """执行步骤"""
    step_id: int
    tool: str
    purpose: str
    status: str = "pending"  # pending, running, completed, failed
    params: Dict[str, Any] = {}
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0


# LangGraph 状态类型定义
class AgentState(TypedDict):
    """Agent 工作流状态"""
    # 输入
    user_query: str
    session_id: str
    current_time: str
    
    # 意图和实体
    intent: Optional[IntentType]
    entities: Optional[ExtractedEntities]
    
    # 工具参数
    tool_params: Optional[ToolParams]
    
    # 执行历史
    steps: List[Dict[str, Any]]
    tool_results: Dict[str, Any]
    
    # 输出
    final_response: str
    success: bool
    error_message: Optional[str]
    
    # 元数据
    fallback_used: bool
    retry_count: int


# 状态字段的注释，用于 LangGraph
class StateAnnotations:
    """状态字段注解"""
    user_query: Annotated[str, "用户输入"]
    session_id: Annotated[str, "会话ID"]
    current_time: Annotated[str, "当前时间"]
    intent: Annotated[Optional[IntentType], "识别到的意图"]
    entities: Annotated[Optional[ExtractedEntities], "提取的实体"]
    tool_params: Annotated[Optional[ToolParams], "工具参数"]
    steps: Annotated[List[Dict], "执行步骤"]
    tool_results: Annotated[Dict, "工具结果"]
    final_response: Annotated[str, "最终响应"]
    success: Annotated[bool, "是否成功"]
    error_message: Annotated[Optional[str], "错误信息"]
    fallback_used: Annotated[bool, "是否使用降级"]
    retry_count: Annotated[int, "重试次数"]