"""
执行计划生成器 - 智能体自我规划系统
根据用户请求自动生成TODO执行计划
"""
import json
import re
from typing import Dict, List, Any, Optional
from ..llm.client import get_llm
from ..utils.logger import logger


class ExecutionPlan:
    """执行计划"""
    
    def __init__(self):
        self.user_query: str = ""
        self.intent: str = ""
        self.entities: Dict[str, Any] = {}
        self.steps: List[Dict[str, Any]] = []  # 执行步骤列表
        self.fallback_plan: List[Dict[str, Any]] = []  # 降级计划
        self.context: Dict[str, Any] = {}  # 执行上下文，存储中间结果
    
    def add_step(self, step_id: int, tool_name: str, params: Dict, purpose: str, required: bool = True):
        """添加执行步骤"""
        self.steps.append({
            "id": step_id,
            "tool": tool_name,
            "params": params,
            "purpose": purpose,
            "required": required,
            "status": "pending",  # pending, running, completed, failed, skipped
            "result": None,
            "error": None
        })
    
    def add_fallback(self, tool_name: str, params: Dict, trigger_on: str):
        """添加降级步骤"""
        self.fallback_plan.append({
            "tool": tool_name,
            "params": params,
            "trigger_on": trigger_on,  # 触发条件
            "status": "pending"
        })
    
    def get_next_step(self) -> Optional[Dict]:
        """获取下一个待执行的步骤"""
        for step in self.steps:
            if step["status"] == "pending":
                return step
        return None
    
    def mark_step_running(self, step_id: int):
        """标记步骤为运行中"""
        for step in self.steps:
            if step["id"] == step_id:
                step["status"] = "running"
                break
    
    def mark_step_completed(self, step_id: int, result: Any):
        """标记步骤为完成"""
        for step in self.steps:
            if step["id"] == step_id:
                step["status"] = "completed"
                step["result"] = result
                break
    
    def mark_step_failed(self, step_id: int, error: str):
        """标记步骤为失败"""
        for step in self.steps:
            if step["id"] == step_id:
                step["status"] = "failed"
                step["error"] = error
                break
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "user_query": self.user_query,
            "intent": self.intent,
            "entities": self.entities,
            "steps": self.steps,
            "fallback_plan": self.fallback_plan,
            "completed_count": sum(1 for s in self.steps if s["status"] == "completed"),
            "total_count": len(self.steps)
        }


class PlanGenerator:
    """执行计划生成器"""
    
    # 可用工具及其用途
    TOOL_USAGES = {
        "parse_date": {
            "purpose": "解析自然语言日期",
            "triggers": ["明天", "后天", "下周一", "3月15日", "周末", "下周"]
        },
        "get_station_by_city": {
            "purpose": "查询城市附近的火车站",
            "triggers": ["火车票", "高铁", "动车", "去某地"]
        },
        "get_train_tickets": {
            "purpose": "查询火车票余票",
            "triggers": ["火车票", "高铁票", "动车票"]
        },
        "get_weather": {
            "purpose": "查询天气预报",
            "triggers": ["天气", "温度", "下雨", "晴天"]
        },
        "search_attractions": {
            "purpose": "搜索景点美食",
            "triggers": ["景点", "美食", "网红", "好玩", "旅游"]
        },
        "web_search": {
            "purpose": "通用搜索（降级备用）",
            "triggers": []
        }
    }
    
    def __init__(self):
        self.llm = get_llm()
    
    def generate_plan(self, user_query: str) -> ExecutionPlan:
        """生成执行计划"""
        plan = ExecutionPlan()
        plan.user_query = user_query
        
        try:
            # 1. 解析实体（出发地、目的地、日期等）
            entities = self._extract_entities(user_query)
            plan.entities = entities
            
            # 2. 判断意图
            intent = self._determine_intent(user_query, entities)
            plan.intent = intent
            
            # 3. 生成执行步骤
            steps = self._generate_steps(user_query, entities, intent)
            for i, step in enumerate(steps, 1):
                plan.add_step(
                    step_id=i,
                    tool_name=step["tool"],
                    params=step.get("params", {}),
                    purpose=step["purpose"],
                    required=step.get("required", True)
                )
            
            # 4. 生成降级计划
            fallback_plan = self._generate_fallback_plan(user_query, entities, intent)
            for fb in fallback_plan:
                plan.add_fallback(
                    tool_name=fb["tool"],
                    params=fb.get("params", {}),
                    trigger_on=fb.get("trigger_on", "error")
                )
            
            logger.info(f"生成执行计划: {len(plan.steps)} 步骤, {len(plan.fallback_plan)} 降级")
            
        except Exception as e:
            logger.error(f"生成执行计划失败: {e}")
            # 返回空计划
            plan.intent = "unknown"
        
        return plan
    
    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """提取实体信息"""
        entities = {
            "origin": None,      # 出发地
            "destination": None,  # 目的地
            "date": None,        # 日期
            "train_type": None, # 火车类型
            "keyword": None      # 搜索关键词
        }
        
        # 使用LLM提取实体
        prompt = f"""分析用户查询，提取关键信息。

用户查询: {query}

请从以下类别中提取信息：
- 出发地：用户从哪里出发（如"从北京"、"北京到"）
- 目的地：用户要去哪里（如"到上海"、"去杭州"）
- 日期：用户说的时间（如"明天"、"周末"）
- 火车类型：高铁/动车/普快（如果有）
- 关键词：景点/美食搜索关键词

请直接输出JSON，不要其他内容：
{{
    "origin": "出发地或null",
    "destination": "目的地或null", 
    "date": "日期描述或null",
    "train_type": "高铁/动车/K/或null",
    "keyword": "搜索关键词或null"
}}
"""
        try:
            # 使用LLM提取实体 - MiniMaxClient使用chat方法
            prompt = f"""分析用户查询，提取关键信息。

用户查询: {query}

请从以下类别中提取信息：
- 出发地：用户从哪里出发（如"从北京"、"北京到"）
- 目的地：用户要去哪里（如"到上海"、"去杭州"）
- 日期：用户说的时间（如"明天"、"周末"）
- 火车类型：高铁/动车/普快（如果有）
- 关键词：景点/美食搜索关键词

请直接输出JSON，不要其他内容：
{{
    "origin": "出发地或null",
    "destination": "目的地或null", 
    "date": "日期描述或null",
    "train_type": "高铁/动车/K/或null",
    "keyword": "搜索关键词或null"
}}
"""
            resp = self.llm.chat(prompt, query)
            content = resp if isinstance(resp, str) else str(resp)
            
            # 提取JSON
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                extracted = json.loads(match.group())
                for k, v in extracted.items():
                    if v and v != "null":
                        entities[k] = v
        except Exception as e:
            logger.error(f"实体提取失败: {e}")
        
        # 简单规则补充提取
        query_clean = query.replace("去", "到").replace("从", "").replace("出发", "")
        
        # 尝试匹配 "XXX到XXX" 模式
        to_match = re.search(r'([^\s,，。到]+)到([^\s,，。]+)', query_clean)
        if to_match and not entities["destination"]:
            entities["origin"] = entities["origin"] or to_match.group(1)
            entities["destination"] = entities["destination"] or to_match.group(2)
        
        # 尝试匹配日期关键词
        date_keywords = ["明天", "后天", "大后天", "今天", "昨天", "周末", "下周", "这周"]
        for kw in date_keywords:
            if kw in query and not entities["date"]:
                entities["date"] = kw
                break
        
        return entities
    
    def _determine_intent(self, query: str, entities: Dict) -> str:
        """判断用户意图"""
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ["火车票", "高铁", "动车", "票"]):
            return "train_tickets"
        elif any(kw in query_lower for kw in ["天气", "温度", "下雨", "晴天"]):
            return "weather"
        elif any(kw in query_lower for kw in ["景点", "美食", "好玩", "旅游", "网红"]):
            return "attractions"
        elif "交通" in query_lower:
            return "transport"
        else:
            return "general"
    
    def _generate_steps(self, query: str, entities: Dict, intent: str) -> List[Dict]:
        """生成执行步骤"""
        steps = []
        step_counter = 1
        
        # === 火车票查询 ===
        if intent == "train_tickets":
            # 1. 如果有出发地，先查找火车站
            if entities.get("origin"):
                steps.append({
                    "tool": "get_station_by_city",
                    "params": {"city": entities["origin"]},
                    "purpose": f"查找{entities['origin']}附近的火车站",
                    "required": True
                })
            
            # 2. 如果有目的地，查找火车站
            if entities.get("destination"):
                steps.append({
                    "tool": "get_station_by_city", 
                    "params": {"city": entities["destination"]},
                    "purpose": f"查找{entities['destination']}附近的火车站",
                    "required": True
                })
            
            # 3. 解析日期
            if entities.get("date"):
                steps.append({
                    "tool": "parse_date",
                    "params": {"date_text": entities["date"]},
                    "purpose": f"解析日期'{entities['date']}'",
                    "required": True
                })
            
            # 4. 查询火车票（条件都满足时）
            if entities.get("origin") and entities.get("destination") and entities.get("date"):
                steps.append({
                    "tool": "get_train_tickets",
                    "params": {
                        "date": "{{parse_date.result}}",  # 占位，实际执行时替换
                        "from_station": "{{origin_station}}",
                        "to_station": "{{destination_station}}",
                        "train_type": entities.get("train_type", "G")
                    },
                    "purpose": "查询火车票",
                    "required": True
                })
        
        # === 天气查询 ===
        elif intent == "weather":
            if entities.get("destination") or entities.get("origin"):
                city = entities.get("destination") or entities.get("origin")
                steps.append({
                    "tool": "get_weather",
                    "params": {"city": city},
                    "purpose": f"查询{city}天气",
                    "required": True
                })
        
        # === 景点搜索 ===
        elif intent == "attractions":
            if entities.get("destination"):
                steps.append({
                    "tool": "search_attractions",
                    "params": {
                        "city": entities["destination"],
                        "keyword": entities.get("keyword", "景点")
                    },
                    "purpose": f"搜索{entities['destination']}的{entities.get('keyword', '景点')}",
                    "required": True
                })
        
        # === 通用搜索（降级）===
        else:
            steps.append({
                "tool": "web_search",
                "params": {"query": query},
                "purpose": "通用搜索",
                "required": False
            })
        
        return steps
    
    def _generate_fallback_plan(self, query: str, entities: Dict, intent: str) -> List[Dict]:
        """生成降级计划"""
        fallback = []
        
        if intent == "train_tickets":
            origin = entities.get("origin", "")
            destination = entities.get("destination", "")
            date = entities.get("date", "")
            if origin and destination:
                fallback.append({
                    "tool": "web_search",
                    "params": {"query": f"{origin}到{destination}火车票 {date}"},
                    "trigger_on": "get_train_tickets_failed"
                })
        
        elif intent == "weather":
            city = entities.get("destination") or entities.get("origin")
            if city:
                fallback.append({
                    "tool": "web_search",
                    "params": {"query": f"{city}天气"},
                    "trigger_on": "get_weather_failed"
                })
        
        elif intent == "attractions":
            city = entities.get("destination")
            if city:
                fallback.append({
                    "tool": "web_search",
                    "params": {"query": f"{city}景点推荐"},
                    "trigger_on": "search_attractions_failed"
                })
        
        return fallback


# 全局计划生成器
_planner = None


def get_planner() -> PlanGenerator:
    """获取计划生成器单例"""
    global _planner
    if _planner is None:
        _planner = PlanGenerator()
    return _planner
