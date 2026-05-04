"""
智能执行计划生成器 - 增强版
核心功能：
1. 上下文感知的时间解析
2. 工具链自动补全
3. 智能参数推断
4. 失败自纠正机制
"""
import json
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from ..llm.client import get_llm
from ..utils.logger import logger
from .time_context import get_time_context


class IntentType(Enum):
    """意图类型"""
    TRAIN_TICKETS = "train_tickets"
    WEATHER = "weather"
    ATTRACTIONS = "attractions"
    TRANSPORT = "transport"
    HOTEL = "hotel"
    GENERAL = "general"
    CAPABILITY = "capability"  # 能力查询
    TRIP_PLAN = "trip_plan"  # 旅行规划
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """实体信息"""
    type: str  # origin, destination, date, train_type, keyword
    value: str
    confidence: float = 1.0  # 置信度
    normalized: Optional[str] = None  # 标准化后的值


@dataclass
class ExecutionStep:
    """执行步骤"""
    id: int
    tool: str
    params: Dict[str, Any]
    purpose: str
    required: bool = True
    depends_on: Optional[int] = None  # 依赖的前置步骤
    retry_on_fail: bool = True  # 失败时是否重试
    fallback: Optional[Dict] = None  # 降级配置
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "tool": self.tool,
            "params": self.params,
            "purpose": self.purpose,
            "required": self.required,
            "depends_on": self.depends_on,
            "retry_on_fail": self.retry_on_fail,
            "fallback": self.fallback
        }


class SmartPlanner:
    """
    智能执行计划生成器
    
    特点：
    1. 先理解用户需求，再规划执行步骤
    2. 自动推断缺失参数
    3. 支持条件分支
    4. 内置常见模式模板
    """
    
    # 常见意图模式
    INTENT_PATTERNS = {
        IntentType.TRAIN_TICKETS: [
            r"火车票", r"高铁", r"动车", r"普快", r"坐火车",
            r"到.*去", r"去.*要"
        ],
        IntentType.WEATHER: [
            r"天气", r"温度", r"下雨", r"晴天", r"冷不冷",
            r"热不热", r"穿什么"
        ],
        IntentType.ATTRACTIONS: [
            r"景点", r"美食", r"好玩", r"旅游", r"网红",
            r"推荐", r"值得去", r"附近", r"周边",
            r"有什么好吃的", r"有什么好玩", r"好玩吗",
            r"游玩攻略", r"打卡"
        ],
        IntentType.TRANSPORT: [
            r"交通", r"怎么去", r"如何去", r"多远"
        ],
        IntentType.HOTEL: [
            r"酒店", r"住宿", r"住哪", r"宾馆"
        ],
        IntentType.CAPABILITY: [
            r"有哪些能力", r"有什么功能", r"你能做什么",
            r"能帮我.*", r"你会.*", r"是什么"
        ],
        IntentType.TRIP_PLAN: [
            r"规划", r"帮我安排", r"行程", r"旅游攻略",
            r"游玩方案", r"去玩", r"旅游", r"旅行",
            r"帮我制定", r"推荐.*路线", r"三日游", r"两天游",
            r"一日游", r"周末.*玩"
        ]
    }
    
    # 城市到火车站的常用映射
    CITY_STATION_MAP = {
        "沙县": ["三明北站", "沙县站"],
        "宁波": ["宁波站", "宁波东站"],
        "福州": ["福州站", "福州南站"],
        "厦门": ["厦门北站", "厦门站"],
        "杭州": ["杭州东站", "杭州站"],
        "上海": ["上海虹桥站", "上海站"],
        "北京": ["北京南站", "北京站"],
        "深圳": ["深圳北站", "深圳站"],
        "广州": ["广州南站", "广州站"],
    }
    
    def __init__(self):
        self.llm = get_llm()
        self.time_context = get_time_context()
    
    def generate_plan(self, user_query: str) -> Dict:
        """
        生成执行计划
        
        返回包含以下内容的字典：
        - intent: 意图类型
        - entities: 提取的实体
        - steps: 执行步骤列表
        - context: 需要的上下文信息
        """
        logger.info(f"生成执行计划: {user_query[:50]}...")
        
        # 1. 意图识别
        intent = self._recognize_intent(user_query)

        # 能力查询：走快速路径，避免不必要的LLM实体抽取
        if intent == IntentType.CAPABILITY:
            steps = self._generate_steps(user_query, intent, {}, {})
            return {
                "intent": intent.value,
                "entities": {},
                "steps": steps,
                "fallback_plan": [],
                "context_needed": {}
            }
        
        # 2. 实体提取（增强版）
        entities = self._extract_entities(user_query)
        
        # 3. 补充缺失的上下文
        context_needed = self._analyze_context_needed(intent, entities)
        
        # 4. 生成执行步骤
        steps = self._generate_steps(user_query, intent, entities, context_needed)
        
        # 5. 生成降级计划
        fallback_plan = self._generate_fallback_plan(intent, entities)
        
        # 6. 如果实体不完整，添加补全步骤
        if context_needed.get("need_stations"):
            steps = self._add_station_steps(steps, entities)
        
        if context_needed.get("need_date"):
            steps = self._add_date_step(steps, entities)
        
        return {
            "intent": intent.value,
            "entities": entities,
            "steps": steps,
            "fallback_plan": fallback_plan,
            "context_needed": context_needed
        }
    
    def _recognize_intent(self, query: str) -> IntentType:
        """识别用户意图"""
        query_lower = query.lower()
        
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent_type
        
        return IntentType.GENERAL
    
    def _extract_entities(self, query: str) -> Dict[str, Entity]:
        """
        提取实体 - 增强版
        
        使用规则 + LLM 混合方式
        """
        entities = {}
        
        # === 时间上下文感知 ===
        # 首先获取当前时间
        current_date = self.time_context.get_today()
        
        # === 规则提取 ===
        query_clean = query.replace("去", "到").replace("从", "").replace("出发", "")
        
        # 使用更简单的方法：先用正则提取日期，其他依赖LLM
        # 提取日期
        date_patterns = [
            r"今天", r"明日", r"明天", r"后天", r"大后天",
            r"昨天", r"前天", r"下周", r"本周", r"周末",
            r"\d{1,2}月\d{1,2}", r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, query)
            if date_match:
                date_text = date_match.group()
                entities["date"] = Entity(
                    type="date",
                    value=date_text,
                    confidence=0.9
                )
                break
        
        # 对于出发地和目的地，直接使用LLM提取
        # 这样更可靠
        llm_entities = self._llm_extract_entities(query)
        for k, v in llm_entities.items():
            if k not in entities:
                entities[k] = v
        
        # 如果LLM也没提取到，尝试简单规则
        if "origin" not in entities or "destination" not in entities:
            # 尝试"XXX到XXX"模式
            to_match = re.search(r"([^\s，。,\d]{1,6})到([^\s，。,\d]{1,6})", query)
            if to_match:
                origin_val = to_match.group(1).strip()
                dest_val = to_match.group(2).strip()
                
                # 清理
                origin_val = origin_val.strip("从查帮")
                dest_val = re.sub(r"(的高铁|的火车|的动车|票|的|玩|天气|景点|美食)$", "", dest_val)
                
                if "origin" not in entities and 2 <= len(origin_val) <= 6:
                    entities["origin"] = Entity(type="origin", value=origin_val, confidence=0.7)
                if "destination" not in entities and 2 <= len(dest_val) <= 6:
                    entities["destination"] = Entity(type="destination", value=dest_val, confidence=0.7)
        
        # ========== 新增：处理景点查询的"XX附近"、"XX周边"模式 ==========
        # 例如："舟山附近的景点" -> 提取"舟山"作为目的地
        if "destination" not in entities:
            # 尝试"XXX附近"、"XXX周边"模式
            nearby_patterns = [
                r"(.+?)附近的(.+?)",
                r"(.+?)周边的(.+?)",
                r"(.+?)有什么好玩的",
                r"(.+?)有什么好吃的",
                r"推荐(.+?)的(.+?)",
                r"(.+?)游玩攻略",
            ]
            for pattern in nearby_patterns:
                match = re.search(pattern, query)
                if match:
                    city = match.group(1).strip()
                    # 清理常见无关词
                    city = re.sub(r"(帮我|请|想问|想问下|想知道|想问一下)$", "", city)
                    if city and 2 <= len(city) <= 6:
                        entities["destination"] = Entity(type="destination", value=city, confidence=0.8)
                        break
        
        # 提取日期
        date_patterns = [
            r"今天", r"明日", r"明天", r"后天", r"大后天",
            r"昨天", r"前天", r"下周", r"本周", r"周末",
            r"\d{1,2}月\d{1,2}", r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, query)
            if date_match:
                date_text = date_match.group()
                entities["date"] = Entity(
                    type="date",
                    value=date_text,
                    confidence=0.9
                )
                break
        
        # 提取火车类型
        if "高铁" in query or "G" in query:
            entities["train_type"] = Entity(
                type="train_type",
                value="G",
                confidence=1.0
            )
        elif "动车" in query or "D" in query:
            entities["train_type"] = Entity(
                type="train_type",
                value="D",
                confidence=1.0
            )
        elif "普通" in query or "K" in query:
            entities["train_type"] = Entity(
                type="train_type",
                value="K",
                confidence=1.0
            )
        
        # 提取预算
        budget_match = re.search(r"(\d+)\s*[元块]", query)
        if budget_match:
            entities["budget"] = Entity(
                type="budget",
                value=budget_match.group(1),
                confidence=0.9
            )
        
        # 提取关键词
        keyword_patterns = {
            "景点": ["景点", "好玩", "值得去"],
            "美食": ["美食", "好吃", "特色", "小吃"],
            "网红": ["网红", "打卡"]
        }
        for kw, patterns in keyword_patterns.items():
            for p in patterns:
                if p in query:
                    entities["keyword"] = Entity(
                        type="keyword",
                        value=kw,
                        confidence=0.8
                    )
                    break
        
        # === LLM 补充提取 ===
        # 如果规则提取的不够完整，用 LLM 补充
        if len(entities) < 2:
            llm_entities = self._llm_extract_entities(query)
            for k, v in llm_entities.items():
                if k not in entities:
                    entities[k] = v
        
        # === 智能推断 ===
        # 如果有目的地但没有出发地，可以尝试推断
        if "destination" in entities and "origin" not in entities:
            # 这里可以后续添加"当前位置"推断
            pass
        
        logger.info(f"提取实体: {[(k, v.value) for k, v in entities.items()]}")
        return entities
    
    def _llm_extract_entities(self, query: str) -> Dict[str, Entity]:
        """使用 LLM 补充提取实体 - 增强版"""
        # 获取当前日期
        current_date = self.time_context.get_today()
        current_formatted = self.time_context.get_today_formatted()
        
        try:
            prompt = f"""你是实体提取专家。从用户查询中提取旅行相关实体。

【重要】当前日期是: {current_formatted} ({current_date})
明天 = {current_date} + 1天
后天 = {current_date} + 2天

用户查询: {query}

【提取规则】
1. origin（出发地）：用户说"从X出发"、"从X去"，X是出发地
2. destination（目的地）：用户说"去X"、"到X"、"X附近"、"X周边"，X是目的地
3. date（日期）：如"明天"、"后天"、"3月15日"、"三天两夜"等
4. train_type：G=高铁，D=动车，K=普快
5. keyword：搜索关键词，如"景点"、"美食"、"酒店"等
6. budget：预算，如"300元"、"500块"

【火车票查询示例】
- "查一下明天北京到上海的高铁" → origin=北京, destination=上海, date=明天, train_type=G
- "帮我买一张去杭州的火车票" → destination=杭州, date=需要询问
- "后天从三明北到宁波有票吗" → origin=三明北, destination=宁波, date=后天

【景点查询示例】
- "舟山附近的景点" → destination=舟山, keyword=景点
- "杭州有什么好玩的地方" → destination=杭州, keyword=景点
- "上海周边美食推荐" → destination=上海, keyword=美食

【旅行规划示例】
- "我想去舟山玩，帮我规划一下" → destination=舟山
- "去杭州旅游三天，预算是2000元" → destination=杭州, date=三天, budget=2000
- "周末去上海玩两天" → destination=上海, date=周末
- "帮我安排一个去北京的三日游" → destination=北京, date=三日游

直接返回JSON格式，不要其他内容：
{{
    "origin": "出发城市或null",
    "destination": "目的城市或null", 
    "date": "日期描述或null",
    "train_type": "G/D/K或null",
    "keyword": "关键词或null",
    "budget": "预算数字或null"
}}
"""
            resp = self.llm.chat(prompt, "")
            content = resp if isinstance(resp, str) else str(resp)
            
            # 解析 JSON
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                extracted = json.loads(match.group())
                entities = {}
                
                for key, value in extracted.items():
                    if value and value != "null":
                        entities[key] = Entity(
                            type=key,
                            value=value,
                            confidence=0.8  # LLM 提取的置信度
                        )
                
                return entities
        except Exception as e:
            logger.error(f"LLM 实体提取失败: {e}")
        
        return {}
    
    def _analyze_context_needed(self, intent: IntentType, 
                                entities: Dict[str, Entity]) -> Dict[str, bool]:
        """分析需要补充的上下文"""
        needed = {
            "need_stations": False,
            "need_date": False,
            "need_city_info": False
        }
        
        # 火车票查询需要火车站信息
        if intent == IntentType.TRAIN_TICKETS:
            if "origin" in entities or "destination" in entities:
                needed["need_stations"] = True
            if "date" not in entities:
                needed["need_date"] = True
        
        # 天气查询需要确认城市
        elif intent == IntentType.WEATHER:
            if "destination" not in entities and "origin" not in entities:
                needed["need_city_info"] = True
        
        return needed
    
    def _generate_steps(self, query: str, intent: IntentType, 
                       entities: Dict[str, Entity],
                       context_needed: Dict[str, bool]) -> List[Dict]:
        """生成执行步骤"""
        steps = []
        step_id = 1
        
        # === 火车票查询流程 ===
        if intent == IntentType.TRAIN_TICKETS:
            # 步骤：日期解析
            if "date" in entities or context_needed.get("need_date"):
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="parse_date",
                    params={"date_text": entities.get("date", Entity("", "")).value if "date" in entities else "今天"},
                    purpose="解析出行日期",
                    required=True
                ).to_dict())
                step_id += 1
            
            # 步骤：查询火车站
            for loc_type in ["origin", "destination"]:
                if loc_type in entities:
                    city = entities[loc_type].value
                    steps.append(ExecutionStep(
                        id=step_id,
                        tool="get_station_by_city",
                        params={"city": city},
                        purpose=f"查找{city}的火车站",
                        required=True
                    ).to_dict())
                    step_id += 1
            
            # 步骤：查询火车票
            if "origin" in entities and "destination" in entities:
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="get_train_tickets",
                    params={
                        "date": "{{parse_date.result}}",
                        "from_station": "{{origin_station}}",
                        "to_station": "{{destination_station}}",
                        "train_type": entities.get("train_type", Entity("", "G")).value if "train_type" in entities else "G"
                    },
                    purpose="查询火车票",
                    required=True
                ).to_dict())
        
        # === 天气查询流程 ===
        elif intent == IntentType.WEATHER:
            city = (entities.get("destination") or entities.get("origin") or Entity("", "")).value
            if city:
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="get_weather",
                    params={"city": city},
                    purpose=f"查询{city}天气",
                    required=True
                ).to_dict())
        
        # === 景点查询流程 ===
        elif intent == IntentType.ATTRACTIONS:
            city = (entities.get("destination") or Entity("", "")).value
            
            # 如果没有提取到目的地城市，尝试从关键词中提取
            if not city and "keyword" in entities:
                keyword_val = entities["keyword"].value
                # 从关键词如"舟山景点"中提取城市名
                # 常见模式：城市名+景点/美食/酒店
                city_match = re.search(r"^(.{2,6})(景点|美食|酒店|好玩|附近|周边)", keyword_val)
                if city_match:
                    city = city_match.group(1)
                    # 更新keyword
                    keyword_match = re.search(r"(景点|美食|酒店|好玩|网红)", keyword_val)
                    if keyword_match:
                        entities["keyword"].value = keyword_match.group(1)
            
            # 如果还是没有城市，尝试从查询语句中提取
            if not city:
                # 尝试匹配"XXX附近"、"XXX周边"等模式
                nearby_match = re.search(r"^(.{2,6})(附近|周边|有什么好吃|有什么好玩)", query)
                if nearby_match:
                    city = nearby_match.group(1)
            
            keyword = (entities.get("keyword") or Entity("", "景点")).value
            
            if city:
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="search_attractions",
                    params={"city": city, "keyword": keyword},
                    purpose=f"搜索{city}的{keyword}",
                    required=True
                ).to_dict())
            elif keyword:
                # 如果没有城市但有关键词，使用通用搜索
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="web_search",
                    params={"query": f"{keyword}推荐"},
                    purpose=f"搜索{keyword}",
                    required=False
                ).to_dict())
        
        # === 旅行规划流程 ===
        elif intent == IntentType.TRIP_PLAN:
            destination = (entities.get("destination") or Entity("", "")).value
            origin = (entities.get("origin") or Entity("", "")).value
            date_text = (entities.get("date") or Entity("", "今天")).value
            budget = (entities.get("budget") or Entity("", "")).value
            keyword = (entities.get("keyword") or Entity("", "景点")).value
            
            if not destination:
                # 没有目的地，使用通用搜索
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="web_search",
                    params={"query": f"{query} 旅行攻略"},
                    purpose="搜索旅行攻略",
                    required=False
                ).to_dict())
                return steps
            
            # 步骤1: 日期解析
            if date_text:
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="parse_date",
                    params={"date_text": date_text},
                    purpose="解析出行日期",
                    required=True
                ).to_dict())
                step_id += 1
            
            # 步骤2: 查询目的地天气
            steps.append(ExecutionStep(
                id=step_id,
                tool="get_weather",
                params={"city": destination},
                purpose=f"查询{destination}天气",
                required=True
            ).to_dict())
            step_id += 1
            
            # 步骤3: 查询目的地景点
            steps.append(ExecutionStep(
                id=step_id,
                tool="search_attractions",
                params={"city": destination, "keyword": keyword},
                purpose=f"搜索{destination}{keyword}",
                required=True
            ).to_dict())
            step_id += 1
            
            # 步骤4: 如果有出发地，查询交通/火车票
            if origin and origin != destination:
                # 先查询火车站
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="get_station_by_city",
                    params={"city": origin},
                    purpose=f"查找{origin}火车站",
                    required=False
                ).to_dict())
                step_id += 1
                steps.append(ExecutionStep(
                    id=step_id,
                    tool="get_station_by_city",
                    params={"city": destination},
                    purpose=f"查找{destination}火车站",
                    required=False
                ).to_dict())
                step_id += 1
            
            # 步骤5: 通用搜索（获取更多攻略信息）
            steps.append(ExecutionStep(
                id=step_id,
                tool="web_search",
                params={"query": f"{destination}旅游攻略 出行建议"},
                purpose=f"搜索{destination}旅行攻略",
                required=False
            ).to_dict())
        
        # === 能力查询 ===
        elif intent == IntentType.CAPABILITY:
            # 能力查询不需要调用工具，直接回答
            steps.append(ExecutionStep(
                id=step_id,
                tool="capability_info",
                params={"query": query},
                purpose="返回智能体能力信息",
                required=False
            ).to_dict())
        
        # === 通用搜索 ===
        else:
            steps.append(ExecutionStep(
                id=step_id,
                tool="web_search",
                params={"query": entities.get("keyword", Entity("", query)).value if "keyword" in entities else query},
                purpose="通用搜索",
                required=False
            ).to_dict())
        
        return steps
    
    def _add_station_steps(self, steps: List[Dict], 
                          entities: Dict[str, Entity]) -> List[Dict]:
        """添加火车站查询步骤"""
        # 重新组织步骤，确保在查票之前先查站
        station_steps = []
        ticket_step_idx = None
        
        for i, step in enumerate(steps):
            if step["tool"] == "get_train_tickets":
                ticket_step_idx = i
                break
        
        # 如果有查票步骤，先插入查站步骤
        if ticket_step_idx is not None:
            new_steps = []
            station_id = 1
            
            # 先添加日期解析
            for step in steps[:ticket_step_idx]:
                new_steps.append(step)
            
            # 添加查站步骤
            if "origin" in entities:
                new_steps.append({
                    "id": len(new_steps) + 1,
                    "tool": "get_station_by_city",
                    "params": {"city": entities["origin"].value},
                    "purpose": f"查找{entities['origin'].value}火车站",
                    "required": True
                })
            
            if "destination" in entities:
                new_steps.append({
                    "id": len(new_steps) + 1,
                    "tool": "get_station_by_city",
                    "params": {"city": entities["destination"].value},
                    "purpose": f"查找{entities['destination'].value}火车站",
                    "required": True
                })
            
            # 添加日期解析和查票步骤
            for step in steps[ticket_step_idx:]:
                step["id"] = len(new_steps) + 1
                new_steps.append(step)
            
            return new_steps
        
        return steps
    
    def _add_date_step(self, steps: List[Dict], 
                      entities: Dict[str, Entity]) -> List[Dict]:
        """添加日期解析步骤"""
        # 确保日期解析在第一步
        has_date_step = any(s["tool"] == "parse_date" for s in steps)
        
        if not has_date_step:
            # 获取用户输入的日期，如果没有则使用"今天"
            date_text = "今天"
            if "date" in entities and entities["date"].value:
                date_text = entities["date"].value
            
            new_steps = [{
                "id": 1,
                "tool": "parse_date",
                "params": {"date_text": date_text},
                "purpose": f"解析日期: {date_text}",
                "required": True
            }]
            
            for step in steps:
                step["id"] = len(new_steps) + 1
                new_steps.append(step)
            
            return new_steps
        
        return steps
    
    def _generate_fallback_plan(self, intent: IntentType, 
                               entities: Dict[str, Entity]) -> List[Dict]:
        """生成降级计划"""
        fallback = []
        
        origin = entities.get("origin", Entity("", "")).value if "origin" in entities else ""
        destination = entities.get("destination", Entity("", "")).value if "destination" in entities else ""
        date = entities.get("date", Entity("", "")).value if "date" in entities else ""
        
        if intent == IntentType.TRAIN_TICKETS and origin and destination:
            # 使用解析后的日期占位符
            fallback.append({
                "tool": "web_search",
                "params": {"query": f"{origin}到{destination}火车票 {{date}}"},
                "trigger_on": "get_train_tickets_failed",
                "use_parsed_date": True  # 标记需要使用解析后的日期
            })
        
        if intent == IntentType.WEATHER and destination:
            fallback.append({
                "tool": "web_search",
                "params": {"query": f"{destination}天气"},
                "trigger_on": "get_weather_failed"
            })
        
        if intent == IntentType.ATTRACTIONS and destination:
            keyword = entities.get("keyword", Entity("", "景点")).value
            fallback.append({
                "tool": "web_search",
                "params": {"query": f"{destination}{keyword}推荐"},
                "trigger_on": "search_attractions_failed"
            })
        
        return fallback


# 全局计划生成器
_planner = None


def get_smart_planner() -> SmartPlanner:
    """获取智能计划生成器"""
    global _planner
    if _planner is None:
        _planner = SmartPlanner()
    return _planner
