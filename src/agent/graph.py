"""
LangChain Agent 流程 - 智能增强版
整合 SmartPlanner、TimeContext
"""
import json
import re
import asyncio
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .tools import execute_tool, get_all_tools
from .smart_planner import get_smart_planner, IntentType
from .time_context import get_time_context
from .planner import ExecutionPlan  # 兼容旧版本
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
    
    def _baidu_attractions(self, city: str, keyword: str = "景点") -> str:
        """百度景点搜索"""
        try:
            from ..data_sources.baidu_search import BaiduSearchAPI
            api = BaiduSearchAPI()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, api.search(city, keyword))
                        result = future.result()
                else:
                    result = asyncio.run(api.search(city, keyword))
            except:
                result = asyncio.run(api.search(city, keyword))
            
            return json.dumps({"降级搜索": f"{city}{keyword}", "结果": result}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"景点降级失败: {e}")
            return json.dumps({"error": f"景点查询失败: {e}"}, ensure_ascii=False)
    
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

    # ============ 智能计划执行系统 (基于 SmartPlanner) ============
    
    def run_smart(self, user_input: str, history: List[Dict] = None) -> str:
        """
        智能执行 - 使用增强版计划生成器
        
        特点：
        1. 更准确的实体提取
        2. 自动参数修复
        3. 上下文感知
        """
        logger.info(f"智能执行: {user_input[:50]}...")
        
        try:
            # 1. 获取智能计划生成器
            planner = get_smart_planner()
            
            # 2. 生成执行计划
            plan = planner.generate_plan(user_input)
            logger.info(f"意图: {plan['intent']}, 步骤数: {len(plan['steps'])}")
            
            # 3. 执行计划
            results = self._execute_smart_plan(plan)
            
            # 4. 生成回复
            return self._make_response_from_smart_plan(user_input, plan, results)
            
        except Exception as e:
            logger.error(f"智能执行失败: {e}")
            import traceback
            traceback.print_exc()
            return f"抱歉，处理您的请求时出错: {str(e)}"
    
    def _execute_smart_plan(self, plan: Dict) -> Dict:
        """执行智能计划"""
        context = {}
        step_results = {}
        
        for step in plan["steps"]:
            step_id = step["id"]
            tool_name = step["tool"]
            params = step["params"]
            purpose = step["purpose"]
            
            logger.info(f"执行步骤{step_id}: {tool_name} - {purpose}")
            
            # 解析参数中的占位符
            resolved_params = self._resolve_params_smart(params, context)
            
            # 执行工具
            try:
                result = execute_tool(tool_name, resolved_params)
                
                # 解析结果
                try:
                    result_data = json.loads(result)
                except:
                    result_data = {"raw": result}
                
                # 检查错误
                if "error" in result_data:
                    logger.warning(f"步骤{step_id}失败: {result_data.get('error')}")
                    
                    # 尝试自动修复
                    fixed_params = self._try_fix_params(tool_name, resolved_params, result_data)
                    if fixed_params:
                        logger.info(f"尝试修复参数: {resolved_params} -> {fixed_params}")
                        result = execute_tool(tool_name, fixed_params)
                        try:
                            result_data = json.loads(result)
                        except:
                            result_data = {"raw": result}
                    
                    # 如果仍然失败，执行降级
                    if "error" in result_data and plan.get("fallback_plan"):
                        fallback_result = self._execute_fallback(plan["fallback_plan"], tool_name, context)
                        if fallback_result:
                            result_data = fallback_result
                            step_results[step_id] = result_data
                            self._update_context_smart(context, tool_name, result_data, plan.get("entities", {}))
                            continue
                
                step_results[step_id] = result_data
                self._update_context_smart(context, tool_name, result_data, plan.get("entities", {}))
                
            except Exception as e:
                logger.error(f"步骤{step_id}异常: {e}")
                step_results[step_id] = {"error": str(e)}
        
        return {
            "step_results": step_results,
            "context": context,
            "intent": plan.get("intent"),
            "entities": plan.get("entities", {})
        }
    
    def _resolve_params_smart(self, params: Dict, context: Dict) -> Dict:
        """解析参数占位符 - 智能版"""
        resolved = {}
        
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                key = v[2:-2]
                
                # 尝试多种上下文键
                if key in context:
                    resolved[k] = context[key]
                elif f"{key}_name" in context:
                    resolved[k] = context[f"{key}_name"]
                elif f"{key}_station" in context:
                    resolved[k] = context[f"{key}_station"]
                else:
                    resolved[k] = v
            else:
                resolved[k] = v
        
        return resolved
    
    def _try_fix_params(self, tool_name: str, params: Dict, error_result: Dict) -> Optional[Dict]:
        """尝试修复失败的参数"""
        error_msg = error_result.get("error", "")
        
        if tool_name == "get_train_tickets":
            # 尝试从错误信息中提取有效站名
            if "无法找到出发站" in error_msg:
                # 尝试更通用的城市名
                if "from_station" in params:
                    city = params["from_station"]
                    # 去掉县等
                    if "县" in city:
                        params["from_station"] = city.replace("县", "市")
                    return params
            
            if "无法找到到达站" in error_msg:
                if "to_station" in params:
                    city = params["to_station"]
                    if "县" in city:
                        params["to_station"] = city.replace("县", "市")
                    return params
        
        return None
    
    def _update_context_smart(self, context: Dict, tool_name: str, 
                             result_data: Dict, entities: Dict):
        """更新执行上下文 - 智能版"""
        
        if tool_name == "get_station_by_city":
            city = result_data.get("city", "")
            stations = result_data.get("stations", [])
            recommended = result_data.get("recommended", "")
            
            # 判断是出发地还是目的地 - Entity是dataclass
            origin_city = ""
            dest_city = ""
            
            # 获取实体值
            if "origin" in entities:
                if hasattr(entities["origin"], "value"):
                    origin_city = entities["origin"].value
                elif isinstance(entities["origin"], dict):
                    origin_city = entities["origin"].get("value", "")
            
            if "destination" in entities:
                if hasattr(entities["destination"], "value"):
                    dest_city = entities["destination"].value
                elif isinstance(entities["destination"], dict):
                    dest_city = entities["destination"].get("value", "")
            
            if city == origin_city:
                context["origin_station"] = recommended
                context["origin_stations"] = [s.get("name") for s in stations] if stations else []
            elif city == dest_city:
                context["destination_station"] = recommended
                context["destination_stations"] = [s.get("name") for s in stations] if stations else []
        
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
        
        elif tool_name == "capability_info":
            context["capability_info"] = result_data
    
    def _execute_fallback(self, fallback_plan: List[Dict], failed_tool: str, 
                         context: Dict) -> Optional[Dict]:
        """执行降级计划"""
        for fb in fallback_plan:
            if fb.get("trigger_on", "").replace("_failed", "") in failed_tool:
                try:
                    result = execute_tool(fb["tool"], fb.get("params", {}))
                    return json.loads(result) if "{" in result else {"raw": result}
                except Exception as e:
                    logger.error(f"降级失败: {e}")
        
        return None
    
    def _make_response_from_smart_plan(self, query: str, plan: Dict, 
                                       results: Dict) -> str:
        """从智能计划结果生成回复"""
        
        # 获取当前日期上下文
        from .time_context import get_time_context
        time_ctx = get_time_context()
        current_date = time_ctx.get_today()
        current_formatted = time_ctx.get_today_formatted()
        
        context = f"用户查询: {query}\n\n"
        context += f"当前日期: {current_formatted} ({current_date})\n"
        context += f"意图: {plan.get('intent', 'unknown')}\n\n"
        
        # 添加解析后的日期信息（如果日期解析步骤执行了）
        step_results = results.get("step_results", {})
        parsed_date_info = ""
        for step_id, result in step_results.items():
            if isinstance(result, str) and "parsed" in result:
                try:
                    date_data = json.loads(result)
                    if date_data.get("parsed"):
                        parsed_date_info = f"用户查询的日期: {date_data['parsed']} ({date_data.get('weekday', '')})\n"
                        context += parsed_date_info
                except:
                    pass
        
        # 添加各步骤结果
        context += "查询结果:\n"
        
        # 火车票结果
        if "train_tickets" in results.get("context", {}):
            tickets = results["context"]["train_tickets"]
            context += f"\n### 火车票\n{json.dumps(tickets, ensure_ascii=False, indent=2)}\n"
        
        # 天气结果
        if "weather" in results.get("context", {}):
            weather = results["context"]["weather"]
            context += f"\n### 天气\n{json.dumps(weather, ensure_ascii=False, indent=2)}\n"
        
        # 景点结果
        if "attractions" in results.get("context", {}):
            attractions = results["context"]["attractions"]
            context += f"\n### 景点\n{json.dumps(attractions, ensure_ascii=False, indent=2)}\n"
        
        # 能力查询结果
        if "capability_info" in results.get("context", {}):
            cap = results["context"]["capability_info"]
            if isinstance(cap, dict) and cap.get("type") == "capability_info":
                return """🎯 **旅行规划助手 - 我的能力**

您好！我是您的智能旅行规划助手，可以为您提供以下服务：

🚄 **火车票查询**
- 查询12306火车票余票信息
- 支持高铁(G)、动车(D)、普快(K)
- 示例：帮我查一下明天北京到上海的高铁票

🌤️ **天气查询**
- 查询指定城市15天天气预报
- 支持相对日期：明天、后天、下周等
- 示例：后天杭州天气怎么样

🎯 **景点推荐**
- 推荐热门景点和网红打卡地
- 周边美食推荐
- 示例：上海有什么好玩的地方

🔍 **智能问答**
- 回答各类旅行相关问题
- 行程规划建议
- 注意事项提醒

📅 **日期理解**
- 明天、后天、大后天
- 下周一、周末
- 具体日期：3月15日

---

💡 **使用示例**：
- 帮我查一下明天北京到上海的高铁票
- 后天杭州天气怎么样
- 上海有什么好玩的地方
- 帮我规划一个去厦门的三天两夜旅行

有什么我可以帮您的吗？"""
        
        # 检查是否有失败
        has_error = False
        for step_id, result in step_results.items():
            if isinstance(result, dict) and "error" in result:
                has_error = True
                break
        
        prompt = f"""你是友好的旅行助手。根据以下查询结果回答用户：

{context}

重要提醒：
- 当前日期是 {current_date} ({current_formatted})
- 用户问的是"明天"的天气，明天就是 {current_date} 的后一天
- 请根据用户的问题正确回答对应日期的天气
- 例如：如果用户问"明天天气怎么样"，而今天是3月14日，那明天就是3月15日

要求：
1. 清晰说明查询到了什么信息
2. 如果部分失败，说明哪些失败了并给出建议
3. 使用emoji让回答更生动
4. 直接给出有用信息，不要重复过程
5. 如果查询成功，给出具体的建议（如购票建议、最佳出行方案等）
"""
        try:
            resp = self.llm.invoke([SystemMessage(content=prompt), HumanMessage(content=query)])
            return resp.content if hasattr(resp, 'content') else str(resp)
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            return f"查询完成，但生成回复时出错: {str(e)}"

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