"""
LangChain Agent 流程 - 参考anime-agent设计
"""
import os
import json
import re
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .tools import execute_tool, get_all_tools, get_tool_schemas
from ..llm.prompts import TRAVEL_AGENT_PROMPT
from ..config import ORCH_API_BASE, ORCH_MODEL, ORCH_API_KEY
from ..utils.logger import logger


class TravelAgent:
    """旅行规划Agent - 参考anime-agent"""
    
    def __init__(self):
        # 创建LLM
        self.llm = ChatOpenAI(
            model=ORCH_MODEL,
            temperature=0.7,
            max_tokens=3000,
            base_url=ORCH_API_BASE,
            api_key=ORCH_API_KEY
        )
        
        # 获取工具
        self.tools = get_all_tools()
        self.tool_schemas = get_tool_schemas()
        
        logger.info(f"Agent初始化完成，工具数量: {len(self.tools)}")
        logger.info(f"可用工具: {[t.__name__ for t in self.tools]}")
    
    def run(self, user_input: str, history: List[Dict] = None) -> str:
        """运行Agent - 完整工作流"""
        
        logger.info(f"=== 开始处理用户请求: {user_input[:50]}...")
        
        try:
            # 步骤1: 解析用户请求，提取需要的信息
            params = self._parse_user_request(user_input)
            logger.info(f"解析参数: {params}")
            
            # 步骤2: 根据需求调用相应工具
            tool_results = {}
            
            # 2.1 火车票查询
            if params.get("need_ticket"):
                ticket_info = self._execute_ticket_query(params)
                tool_results["火车票"] = ticket_info
                logger.info(f"火车票查询完成: {ticket_info[:200] if ticket_info else '无'}...")
            
            # 2.2 天气查询
            if params.get("need_weather"):
                weather_info = self._execute_weather_query(params)
                tool_results["天气"] = weather_info
                logger.info(f"天气查询完成: {weather_info[:200] if weather_info else '无'}...")
            
            # 2.3 景点查询
            if params.get("need_attractions"):
                attractions_info = self._execute_attractions_query(params)
                tool_results["景点"] = attractions_info
                logger.info(f"景点查询完成: {attractions_info[:200] if attractions_info else '无'}...")
            
            # 步骤3: 构建完整Prompt，整合所有信息
            final_prompt = self._build_final_prompt(user_input, params, tool_results)
            
            # 步骤4: 调用LLM生成最终回复
            logger.info("调用LLM生成最终回复...")
            messages = [SystemMessage(content=final_prompt)]
            messages.append(HumanMessage(content=user_input))
            
            response = self.llm.invoke(messages)
            final_response = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"最终回复: {final_response[:100]}...")
            return final_response
        
        except Exception as e:
            logger.error(f"Agent运行失败: {e}")
            import traceback
            traceback.print_exc()
            return f"抱歉，处理您的请求时出现问题: {str(e)}"
    
    def _parse_user_request(self, query: str) -> Dict:
        """解析用户请求，提取参数"""
        params = {
            "destination": None,      # 目的地
            "origin": None,           # 出发地
            "date": None,             # 日期
            "days": None,             # 天数
            "budget": None,           # 预算
            "need_weather": False,    # 需要查天气
            "need_ticket": False,     # 需要查车票
            "need_attractions": False # 需要查景点
        }
        
        query_lower = query.lower()
        
        # 提取城市
        cities = self._extract_cities(query)
        if cities:
            # 假设第一个是目的地，最后一个是出发地
            params["destination"] = cities[0]
            if len(cities) > 1:
                params["origin"] = cities[-1]
            elif "从" in query and "出发" in query:
                # 如果用户说"从宁波出发"，需要明确
                pass
        
        # 特别处理"去X"格式
        match = re.search(r'去(.+?)((?:三天|两天|四天|五天)|(?:天)|(?:的|$))', query)
        if match:
            dest = match.group(1).strip()
            if dest and params["destination"] is None:
                params["destination"] = dest
        
        # 提取天数
        days_match = re.search(r'(\d+)\s*天', query)
        if days_match:
            params["days"] = int(days_match.group(1))
        
        # 提取日期
        params["date"] = self._extract_date(query)
        
        # 判断需要什么服务
        params["need_weather"] = "天气" in query or "温度" in query
        params["need_ticket"] = any(kw in query for kw in ["火车", "高铁", "动车", "票", "车次"])
        params["need_attractions"] = any(kw in query for kw in ["景点", "好玩", "美食", "旅游", "推荐", "规划"])
        
        # 如果是规划旅行，默认都需要
        if params["destination"] and not any([params["need_weather"], params["need_ticket"], params["need_attractions"]]):
            params["need_weather"] = True
            params["need_ticket"] = True
            params["need_attractions"] = True
        
        return params
    
    def _extract_cities(self, query: str) -> List[str]:
        """提取城市名"""
        cities = [
            "北京", "上海", "广州", "深圳", "成都", "杭州", "西安", "重庆",
            "南京", "武汉", "天津", "苏州", "郑州", "长沙", "青岛", "沈阳",
            "大连", "厦门", "昆明", "哈尔滨", "长春", "福州", "南昌", "贵阳",
            "太原", "济南", "宁波", "温州", "无锡", "常州", "徐州", "扬州", "镇江"
        ]
        
        found = []
        for city in cities:
            if city in query:
                found.append(city)
        
        # 尝试匹配"从X到Y"格式
        match = re.search(r'从(.+?)到(.+?)(?:的|，|,|$)', query)
        if match:
            origin = match.group(1).strip()
            dest = match.group(2).strip()
            if origin not in found:
                found.insert(0, origin)
            if dest not in found:
                found.append(dest)
        
        return found
    
    def _extract_date(self, query: str) -> Optional[str]:
        """提取日期"""
        from datetime import datetime, timedelta
        
        # 明天/后天/今天
        if "明天" in query:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "后天" in query:
            return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        elif "今天" in query or "今日" in query:
            return datetime.now().strftime("%Y-%m-%d")
        
        # 匹配日期格式如 2026-03-15, 3月15日, 03-15
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', query)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        
        match = re.search(r'(\d{1,2})月(\d{1,2})日', query)
        if match:
            year = datetime.now().year
            return f"{year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"
        
        return None
    
    def _execute_ticket_query(self, params: Dict) -> str:
        """执行火车票查询"""
        origin = params.get("origin") or params.get("from_station")
        destination = params.get("destination") or params.get("to_station")
        date = params.get("date")
        
        if not origin or not destination:
            return "未提供出发地和目的地，无法查询火车票"
        
        if not date:
            from datetime import datetime
            date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"查询火车票: {origin} -> {destination}, 日期: {date}")
        
        try:
            result = execute_tool("get_train_tickets", {
                "date": date,
                "from_station": origin,
                "to_station": destination,
                "train_type": "G"
            })
            return result
        except Exception as e:
            logger.error(f"火车票查询失败: {e}")
            return f"火车票查询失败: {str(e)}"
    
    def _execute_weather_query(self, params: Dict) -> str:
        """执行天气查询"""
        city = params.get("destination")
        if not city:
            return "未提供目的地，无法查询天气"
        
        logger.info(f"查询天气: {city}")
        
        try:
            result = execute_tool("get_weather", {"city": city})
            return result
        except Exception as e:
            logger.error(f"天气查询失败: {e}")
            return f"天气查询失败: {str(e)}"
    
    def _execute_attractions_query(self, params: Dict) -> str:
        """执行景点查询"""
        city = params.get("destination")
        if not city:
            return "未提供目的地，无法查询景点"
        
        logger.info(f"查询景点: {city}")
        
        try:
            # 查询景点
            result = execute_tool("search_attractions", {
                "city": city,
                "keyword": "景点"
            })
            return result
        except Exception as e:
            logger.error(f"景点查询失败: {e}")
            return f"景点查询失败: {str(e)}"
    
    def _build_final_prompt(self, user_query: str, params: Dict, tool_results: Dict) -> str:
        """构建最终Prompt，整合所有信息"""
        
        prompt = f"""你是一个专业的旅行规划助手。请根据以下信息，为用户规划旅行。

## 用户需求
{user_query}

## 解析的信息
- 目的地: {params.get('destination', '未知')}
- 出发地: {params.get('origin', '未知')}
- 出发日期: {params.get('date', '未知')}
- 旅行天数: {params.get('days', '未知')}天
- 预算: {params.get('budget', '未知')}

"""
        
        # 添加工具查询结果
        if tool_results:
            prompt += "## 查询结果\n\n"
            
            if "火车票" in tool_results:
                prompt += f"### 火车票信息\n{tool_results['火车票']}\n\n"
            
            if "天气" in tool_results:
                prompt += f"### 天气信息\n{tool_results['天气']}\n\n"
            
            if "景点" in tool_results:
                prompt += f"### 景点信息\n{tool_results['景点']}\n\n"
        
        prompt += """## 输出要求
1. 根据用户需求，整合以上信息给出合理的行程规划
2. 如果查询结果为空或查询失败，请友好告知用户
3. 行程要具体，包含每日安排
4. 给出实用的建议和注意事项
5. 语言要友好自然，符合中文表达习惯

请开始规划！"""
        
        return prompt


# 全局Agent实例
_agent = None


def get_agent() -> TravelAgent:
    """获取Agent实例"""
    global _agent
    if _agent is None:
        _agent = TravelAgent()
    return _agent