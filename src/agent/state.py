"""
Agent 状态定义
"""
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Agent 状态定义"""
    # 输入
    messages: Annotated[List, add_messages]  # 消息历史
    user_query: str                          # 用户查询
    
    # 意图解析结果
    intent: Dict | None                      # 解析后的意图
    
    # 工具调用结果
    tool_results: Dict | None               # 工具调用结果
    
    # 输出
    final_response: str | None              # 最终回复
    error: str | None                        # 错误信息
    
    # 元数据
    tools_used: List[str]                   # 使用的工具列表
