"""
对话上下文模型
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Message:
    """对话消息"""
    role: str           # "user" or "assistant"
    content: str        # 消息内容
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class ConversationContext:
    """对话上下文"""
    messages: List[Message] = field(default_factory=list)
    user_preferences: Dict = field(default_factory=dict)
    current_travel_plan: Optional[Dict] = None
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """添加消息"""
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(msg)
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """获取最近的消息"""
        return self.messages[-count:]
    
    def clear(self):
        """清空上下文"""
        self.messages.clear()
        self.user_preferences.clear()
        self.current_travel_plan = None
