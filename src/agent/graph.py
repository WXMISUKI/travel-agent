"""
LangChain Agent 流程 - 支持执行计划TODO系统
"""
import json
import re
import asyncio
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .tools import execute_tool, get_all_tools
from .planner import get_planner, ExecutionPlan
from ..config import ORCH_API_BASE, ORCH_MODEL, ORCH_API_KEY
from ..utils.logger import logger


# 工具描述
TOOL_DESCRIPTIONS = """
## 工具说明

1. get_weather - 查询天气（仅支持部分大城市）
2. get_train_tickets - 查询火车票（仅支持火车站）
3. search_attractions - 搜索景点美食
4. web_search - 通用搜索（当其他工具失败时使用）
5. get_current_date - 获取日期
"""


class TravelAgent:
    """旅行规划Agent"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=ORCH_MODEL,
            temperature=0.7,
            max_tokens=3000,
            base_url=ORCH_API_BASE,
            api_key=ORCH_API_KEY
        )
        self.tools = get_all_tools()
        logger.info(f"Agent初始化，工具: {len(self.tools)}")
    
    def run(self, user_input: str, history: List[Dict] = None) -> str:
        logger.info(f"处理: {user_input[:50]}...")
        
        try:
            # 1. 解析意图
            intent = self._parse_intent(user_input)
            tools_needed = intent.get("needed_tools", [])
            logger.info(f"需要工具: {tools_needed}")
            
            results = {}
            
            # 2. 调用工具
            dest = intent.get("destination") or intent.get("city") or ""
            origin = intent.get("origin") or ""
            date = intent.get("date") or "近期"
            
            # 天气
            if "get_weather" in tools_needed and dest:
                results["天气"] = self._call_with_fallback(
                    "get_weather", {"city": dest},
                    fallback=lambda: self._baidu_weather(dest)
                )
            
            # 火车票
            if "get_train_tickets" in tools_needed and origin and dest:
                results["火车票"] = self._call_with_fallback(
                    "get_train_tickets", 
                    {"date": date, "from_station": origin, "to_station": dest},
                    fallback=lambda: self._baidu_transport(origin, dest)
                )
            
            # 景点
            if "search_attractions" in tools_needed and dest:
                results["景点"] = self._call_with_fallback(
                    "search_attractions", {"city": dest, "keyword": "景点"}
                )
            
            # 3. 生成回复
            return self._make_response(user_input, intent, results)
            
        except Exception as e:
            logger.error(f"运行失败: {e}")
            import traceback
            traceback.print_exc()
            return f"抱歉出错: {str(e)}"
    
    def _call_with_fallback(self, tool_name: str, params: dict, fallback) -> str:
        """调用工具，失败时降级"""
        try:
            result = execute_tool(tool_name, params)
            
            # 检查是否失败
            try:
                data = json.loads(result)
                if "error" in data or data.get("status") == "error":
                    logger.warning(f"{tool_name}失败，使用降级")
                    return fallback()
            except:
                pass
            return result
            
        except Exception as e:
            logger.error(f"{tool_name}异常: {e}")
            return fallback()
    
    def _baidu_weather(self, city: str) -> str:
        """百度天气搜索"""
        try:
            from ..data_sources.baidu_search import BaiduSearchAPI
            api = BaiduSearchAPI()
            # 同步调用
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, api.search_weather(city))
                        result = future.result()
                else:
                    result = asyncio.run(api.search_weather(city))
            except:
                result = asyncio.run(api.search_weather(city))
            
            return json.dumps({"降级搜索": f"{city}天气", "结果": result}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"天气降级失败: {e}")
            return json.dumps({"error": f"天气查询失败: {e}"}, ensure_ascii=False)
    
    def _baidu_transport(self, from_city: str, to_city: str) -> str:
        """百度交通搜索"""
        try:
            from ..data_sources.baidu_search import BaiduSearchAPI
            api = BaiduSearchAPI()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, api.search_transport(from_city, to_city))
                        result = future.result()
                else:
                    result = asyncio.run(api.search_transport(from_city, to_city))
            except:
                result = asyncio.run(api.search_transport(from_city, to_city))
            
            return json.dumps({"降级搜索": f"{from_city}到{to_city}交通", "结果": result}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"交通降级失败: {e}")
            return json.dumps({"error": f"交通查询失败: {e}"}, ensure_ascii=False)
    
    def _parse_intent(self, query: str) -> Dict:
        """解析意图"""
        prompt = f"""你是旅行助手。用户问题：{query}

输出JSON包含：city(目的地), origin(出发地), date(日期), needed_tools([get_weather/get_train_tickets/search_attractions])
"""
        try:
            resp = self.llm.invoke([SystemMessage(content=prompt), HumanMessage(content=query)])
            content = resp.content if hasattr(resp, 'content') else str(resp)
            
            # 尝试提取JSON
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error(f"解析失败: {e}")
        
        return {"needed_tools": []}
    
    def _make_response(self, query: str, intent: Dict, results: Dict) -> str:
        """生成回复"""

        context = f"用户: {query}\n\n查询结果:\n"
        for k, v in results.items():
            context += f"\n### {k}\n{v}\n"

        prompt = f"""你是友好的旅行助手。根据以下查询结果回答用户：

{context}

要求：
1. 查询失败时说明情况并给建议
2. 使用emoji
3. 直接回答
"""
        try:
            resp = self.llm.invoke([SystemMessage(content=prompt), HumanMessage(content=query)])
            return resp.content if hasattr(resp, 'content') else str(resp)
        except Exception as e:
            logger.error(f"生成失败: {e}")
            return f"抱歉出错: {str(e)}"

    # ============ 执行计划TODO系统方法 ============

    def create_execution_plan(self, user_query: str) -> ExecutionPlan:
        """创建执行计划"""
        planner = get_planner()
        plan = planner.generate_plan(user_query)
        logger.info(f"创建执行计划: {plan.intent}, 步骤数: {len(plan.steps)}")
        return plan

    def execute_plan(self, plan: ExecutionPlan, context: Dict = None) -> Dict:
        """执行计划，返回执行结果"""
        if context is None:
            context = {}

        results = {
            "intent": plan.intent,
            "entities": plan.entities,
            "steps_executed": [],
            "step_results": {},
            "success": True,
            "final_data": {}
        }

        for step in plan.steps:
            step_id = step["id"]
            tool_name = step["tool"]
            params = step["params"]
            purpose = step["purpose"]

            logger.info(f"执行步骤{step_id}: {tool_name} - {purpose}")

            # 替换参数中的占位符
            params = self._resolve_params(params, context, results)

            # 执行工具
            try:
                result = execute_tool(tool_name, params)
                
                # 解析结果
                try:
                    result_data = json.loads(result)
                except:
                    result_data = {"raw": result}

                # 检查是否失败
                if "error" in result_data:
                    logger.warning(f"步骤{step_id}失败: {result_data.get('error')}")
                    step["status"] = "failed"
                    step["error"] = result_data.get("error")
                    
                    # 执行降级
                    if plan.fallback_plan:
                        fallback_result = self._execute_fallback(plan.fallback_plan, context, results)
                        if fallback_result:
                            results["step_results"][step_id] = fallback_result
                            step["result"] = fallback_result
                            step["status"] = "fallback_success"
                        else:
                            results["success"] = False
                    else:
                        results["success"] = False
                else:
                    step["status"] = "completed"
                    step["result"] = result_data
                    results["step_results"][step_id] = result_data

                    # 更新上下文
                    self._update_context(context, tool_name, result_data, plan.entities)

            except Exception as e:
                logger.error(f"步骤{step_id}异常: {e}")
                step["status"] = "failed"
                step["error"] = str(e)
                results["success"] = False

            results["steps_executed"].append({
                "id": step_id,
                "tool": tool_name,
                "purpose": purpose,
                "status": step["status"]
            })

        # 收集最终数据
        results["final_data"] = context
        return results

    def _resolve_params(self, params: Dict, context: Dict, results: Dict) -> Dict:
        """解析参数中的占位符"""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                # 替换占位符
                key = v[2:-2]
                resolved[k] = context.get(key, v)
            else:
                resolved[k] = v
        return resolved

    def _update_context(self, context: Dict, tool_name: str, result_data: Dict, entities: Dict):
        """更新执行上下文"""
        
        if tool_name == "get_station_by_city":
            city = result_data.get("city", "")
            stations = result_data.get("stations", [])
            
            # 判断是出发地还是目的地的火车站
            origin_city = entities.get("origin", "")
            dest_city = entities.get("destination", "")
            
            if city == origin_city and stations:
                context["origin_station"] = stations[0].get("name", "")
                context["origin_stations"] = [s.get("name") for s in stations]
            elif city == dest_city and stations:
                context["destination_station"] = stations[0].get("name", "")
                context["destination_stations"] = [s.get("name") for s in stations]
        
        elif tool_name == "parse_date":
            parsed = result_data.get("parsed")
            if parsed:
                context["parsed_date"] = parsed
                context["weekday"] = result_data.get("weekday", "")
        
        elif tool_name == "get_train_tickets":
            context["train_tickets"] = result_data
        
        elif tool_name == "get_weather":
            context["weather"] = result_data
        
        elif tool_name == "search_attractions":
            context["attractions"] = result_data

    def _execute_fallback(self, fallback_plan: List[Dict], context: Dict, results: Dict) -> Dict:
        """执行降级计划"""
        for fb in fallback_plan:
            tool_name = fb["tool"]
            params = fb.get("params", {})
            
            logger.info(f"执行降级: {tool_name}")
            
            try:
                result = execute_tool(tool_name, params)
                result_data = json.loads(result) if "{" in result else {"raw": result}
                
                if "error" not in result_data:
                    return result_data
                    
            except Exception as e:
                logger.error(f"降级失败: {e}")
        
        return None

    def run_with_plan(self, user_input: str, history: List[Dict] = None) -> str:
        """使用执行计划模式运行"""
        
        # 1. 创建执行计划
        plan = self.create_execution_plan(user_input)
        
        # 2. 执行计划
        results = self.execute_plan(plan)
        
        # 3. 生成回复
        return self._make_response_from_plan(user_input, plan, results)

    def _make_response_from_plan(self, query: str, plan: ExecutionPlan, results: Dict) -> str:
        """根据执行计划结果生成回复"""
        
        context = f"用户: {query}\n\n"
        
        # 添加执行摘要
        context += f"意图: {plan.intent}\n"
        context += f"实体: {json.dumps(plan.entities, ensure_ascii=False)}\n\n"
        
        # 添加各步骤结果
        context += "执行结果:\n"
        
        for step_id, result in results.get("step_results", {}).items():
            if step_id == "fallback":
                continue
            context += f"\n{json.dumps(result, ensure_ascii=False)}\n"
        
        # 如果有降级结果
        if results.get("fallback_result"):
            context += f"\n降级搜索结果:\n{json.dumps(results['fallback_result'], ensure_ascii=False)}\n"
        
        prompt = f"""你是友好的旅行助手。根据以下执行结果回答用户：

{context}

要求：
1. 清晰说明查询到了什么信息
2. 如果部分失败，说明哪些失败了
3. 使用emoji让回答更生动
4. 直接给出有用信息，不要重复过程
"""
        try:
            resp = self.llm.invoke([SystemMessage(content=prompt), HumanMessage(content=query)])
            return resp.content if hasattr(resp, 'content') else str(resp)
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            return f"查询完成，但生成回复时出错: {str(e)}"


# 全局Agent
_agent = None

def get_agent() -> TravelAgent:
    global _agent
    if _agent is None:
        _agent = TravelAgent()
    return _agent