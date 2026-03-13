"""
MiniMax 客户端
"""
import os
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.outputs import ChatGeneration
from ..config import ORCH_API_BASE, ORCH_MODEL, ORCH_API_KEY
from ..utils.logger import logger


class MiniMaxClient:
    """MiniMax 模型客户端"""
    
    def __init__(self):
        self.client = ChatOpenAI(
            model=ORCH_MODEL,
            temperature=0.7,
            max_tokens=2000,
            base_url=ORCH_API_BASE,
            api_key=ORCH_API_KEY
        )
        
        # 低温度客户端（用于结构化输出）
        self.structured_client = ChatOpenAI(
            model=ORCH_MODEL,
            temperature=0.1,
            max_tokens=1000,
            base_url=ORCH_API_BASE,
            api_key=ORCH_API_KEY
        )
    
    def chat(self, system_prompt: str, user_input: str, 
             history: List[Dict] = None) -> str:
        """发送聊天请求"""
        
        messages = [SystemMessage(content=system_prompt)]
        
        # 添加历史消息
        if history:
            for msg in history[-6:]:  # 最近3轮
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        
        # 添加当前输入
        messages.append(HumanMessage(content=user_input))
        
        try:
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"MiniMax调用失败: {e}")
            return f"抱歉，服务暂时不可用: {str(e)}"
    
    def parse_intent(self, user_input: str, history: List[Dict] = None) -> Dict:
        """解析用户意图"""
        
        from .prompts import INTENT_PROMPT
        
        messages = [SystemMessage(content=INTENT_PROMPT)]
        
        if history:
            for msg in history[-6:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        
        messages.append(HumanMessage(content=f"用户查询：{user_input}"))
        
        try:
            response = self.structured_client.invoke(messages)
            return self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"意图解析失败: {e}")
            return {"intent": {"action": "unknown"}, "error": str(e)}
    
    def format_response(self, user_input: str, data: Dict) -> str:
        """格式化响应"""
        
        from .prompts import FORMAT_PROMPT
        
        messages = [
            SystemMessage(content=FORMAT_PROMPT),
            HumanMessage(content=f"用户查询：{user_input}\n\n数据：{json.dumps(data, ensure_ascii=False)}")
        ]
        
        try:
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"格式化失败: {e}")
            return f"数据已获取：{json.dumps(data, ensure_ascii=False)}"
    
    def _parse_json_response(self, content: str) -> Dict:
        """解析JSON响应"""

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 回退：尝试提取JSON块
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 最终回退
        return {"raw": content, "error": "JSON解析失败"}


# 全局LLM客户端实例
_llm_client = None


def get_llm():
    """获取LLM客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = MiniMaxClient()
    return _llm_client
