"""
FastAPI 后端入口 - 使用执行计划模式
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import json
import asyncio
from typing import Dict, List

from .agent.graph import get_agent
from .agent.tools import execute_tool
from .utils.logger import logger

app = FastAPI(title="旅行规划助手 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return {"name": "旅行规划助手 API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


async def stream_response(message: str, history: list):
    """流式响应 - 执行计划模式"""
    from .agent.graph import get_agent
    
    # 获取Agent
    agent = get_agent()
    
    try:
        yield "data: " + json.dumps({"type": "start"}) + "\n\n"
        
        # 思考过程
        thinking = ["🧠 分析需求..."]
        yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
        
        # ============ 生成执行计划 ============
        try:
            plan = agent.create_execution_plan(message)
        except Exception as e:
            logger.error(f"创建执行计划失败: {e}")
            plan = None
        
        if plan:
            # 显示意图和实体
            thinking.append(f"📋 意图: {plan.intent}")
            
            # 显示提取的实体
            entities_info = []
            if plan.entities.get("origin"):
                entities_info.append(f"出发地: {plan.entities['origin']}")
            if plan.entities.get("destination"):
                entities_info.append(f"目的地: {plan.entities['destination']}")
            if plan.entities.get("date"):
                entities_info.append(f"日期: {plan.entities['date']}")
            
            if entities_info:
                thinking.append("📍 " + ", ".join(entities_info))
            
            yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
            await asyncio.sleep(0.3)
            
            # 显示TODO执行计划
            if plan.steps:
                todo_list = []
                for s in plan.steps:
                    todo_list.append(f"⬜ [{s['id']}] {s['tool']}: {s['purpose']}")
                
                thinking.append("📝 执行计划:")
                yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                yield "data: " + json.dumps({"type": "todo", "items": todo_list}) + "\n"
                await asyncio.sleep(0.3)
            
            # ============ 执行计划 ============
            context = {}
            
            for step in plan.steps:
                step_id = step["id"]
                tool_name = step["tool"]
                params = step["params"]
                purpose = step["purpose"]
                
                # 显示当前步骤
                thinking.append(f"🔄 执行步骤{step_id}: {tool_name}")
                yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                yield "data: " + json.dumps({
                    "type": "step_status",
                    "step_id": step_id,
                    "status": "running",
                    "tool": tool_name,
                    "purpose": purpose
                }) + "\n"
                
                # 替换参数占位符
                params = _resolve_params(params, context)
                
                try:
                    result = execute_tool(tool_name, params)
                    
                    # 尝试解析JSON
                    try:
                        result_data = json.loads(result)
                    except:
                        result_data = {"raw": result}
                    
                    # 检查结果
                    if "error" in result_data:
                        # 失败 - 显示降级信息
                        error_msg = result_data.get("error", "未知错误")
                        thinking.append(f"❌ {tool_name} 失败: {error_msg[:30]}...")
                        yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                        
                        # 执行降级
                        fallback_result = None
                        for fb in plan.fallback_plan:
                            fb_tool = fb["tool"]
                            fb_params = fb.get("params", {})
                            
                            thinking.append(f"🔄 使用降级工具: {fb_tool}")
                            yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                            
                            try:
                                fb_result = execute_tool(fb_tool, fb_params)
                                fb_data = json.loads(fb_result) if "{" in fb_result else {"raw": fb_result}
                                if "error" not in fb_data:
                                    fallback_result = fb_data
                                    thinking.append(f"✅ 降级搜索完成")
                                    break
                            except Exception as fb_e:
                                logger.error(f"降级工具执行失败: {fb_e}")
                        
                        if fallback_result:
                            yield "data: " + json.dumps({
                                "type": "step_status",
                                "step_id": step_id,
                                "status": "fallback_success",
                                "result": fallback_result
                            }) + "\n"
                            _update_context(context, tool_name, fallback_result, plan.entities)
                        else:
                            yield "data: " + json.dumps({
                                "type": "step_status",
                                "step_id": step_id,
                                "status": "failed",
                                "error": result_data.get("error")
                            }) + "\n"
                            thinking.append(f"❌ 步骤{step_id}失败")
                    else:
                        # 成功
                        thinking.append(f"✅ 步骤{step_id}完成: {tool_name}")
                        yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                        yield "data: " + json.dumps({
                            "type": "step_status",
                            "step_id": step_id,
                            "status": "completed",
                            "result": result_data
                        }) + "\n"
                        
                        # 更新上下文
                        _update_context(context, tool_name, result_data, plan.entities)
                        
                except Exception as e:
                    logger.error(f"步骤执行异常: {e}")
                    thinking.append(f"❌ 异常: {str(e)}")
                    yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                    yield "data: " + json.dumps({
                        "type": "step_status",
                        "step_id": step_id,
                        "status": "error",
                        "error": str(e)
                    }) + "\n"
                
                await asyncio.sleep(0.2)
            
            # ============ 生成最终回复 ============
            thinking.append("📝 生成回复...")
            yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
            
            # 构建结果
            results = {}
            for key, value in context.items():
                if key in ["weather", "train_tickets", "attractions"]:
                    results[key] = json.dumps(value, ensure_ascii=False)
            
            # 使用旧的意图解析作为后备
            intent = agent._parse_intent(message)
            response = agent._make_response(message, intent, results)
            
            yield "data: " + json.dumps({"type": "content", "content": response}) + "\n"
            yield "data: " + json.dumps({"type": "done"}) + "\n\n"
        else:
            # 执行计划创建失败，使用旧的流程
            yield "data: " + json.dumps({"type": "thinking", "content": ["🧠 使用传统模式..."]}) + "\n"
            
            intent = agent._parse_intent(message)
            tools = intent.get("needed_tools", [])
            
            dest = intent.get("destination") or intent.get("city") or ""
            origin = intent.get("origin") or ""
            date = intent.get("date") or "近期"
            
            results = {}
            
            if "get_weather" in tools and dest:
                thinking.append(f"🌤️ 查询天气: {dest}")
                yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                results["天气"] = agent._call_with_fallback("get_weather", {"city": dest}, lambda: agent._baidu_weather(dest))
            
            if "get_train_tickets" in tools and origin and dest:
                thinking.append("🚄 查询火车票...")
                yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                results["火车票"] = agent._call_with_fallback("get_train_tickets", {"date": date, "from_station": origin, "to_station": dest}, lambda: agent._baidu_transport(origin, dest))
            
            if "search_attractions" in tools and dest:
                thinking.append(f"🎯 查询景点: {dest}")
                yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
                results["景点"] = agent._call_with_fallback("search_attractions", {"city": dest, "keyword": "景点"})
            
            thinking.append("📝 生成回复...")
            yield "data: " + json.dumps({"type": "thinking", "content": thinking}) + "\n"
            
            response = agent._make_response(message, intent, results)
            yield "data: " + json.dumps({"type": "content", "content": response}) + "\n"
            yield "data: " + json.dumps({"type": "done"}) + "\n\n"
        
    except Exception as e:
        logger.error(f"流式错误: {e}")
        import traceback
        traceback.print_exc()
        yield "data: " + json.dumps({"type": "error", "content": str(e)}) + "\n"


def _resolve_params(params: Dict, context: Dict) -> Dict:
    """解析参数占位符"""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
            key = v[2:-2]
            resolved[k] = context.get(key, v)
        else:
            resolved[k] = v
    return resolved


def _update_context(context: Dict, tool_name: str, result_data: Dict, entities: Dict):
    """更新执行上下文"""
    if tool_name == "get_station_by_city":
        city = result_data.get("city", "")
        stations = result_data.get("stations", [])
        
        origin_city = entities.get("origin", "")
        dest_city = entities.get("destination", "")
        
        if city == origin_city and stations:
            context["origin_station"] = stations[0].get("name", "")
        elif city == dest_city and stations:
            context["destination_station"] = stations[0].get("name", "")
    
    elif tool_name == "parse_date":
        parsed = result_data.get("parsed")
        if parsed:
            context["parsed_date"] = parsed
    
    elif tool_name == "get_train_tickets":
        context["train_tickets"] = result_data
    
    elif tool_name == "get_weather":
        context["weather"] = result_data
    
    elif tool_name == "search_attractions":
        context["attractions"] = result_data


@app.post("/chat/stream")
async def chat_stream(request: Request):
    try:
        body = await request.json()
        msg = body.get("message", "")
        if not msg:
            return JSONResponse(status_code=400, content={"error": "message不能为空"})
        
        logger.info(f"请求: {msg[:50]}")
        
        return StreamingResponse(
            stream_response(msg, body.get("history", [])),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    except Exception as e:
        logger.error(f"错误: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
        msg = body.get("message", "")
        if not msg:
            return JSONResponse(status_code=400, content={"error": "message不能为空"})
        
        agent = get_agent()
        response = agent.run(user_input=msg)
        return JSONResponse(content={"response": response})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/tools")
async def list_tools():
    from .agent.tools import AVAILABLE_TOOLS
    return {"tools": [{"name": k, "description": v["description"]} for k, v in AVAILABLE_TOOLS.items()]}


logger.info("API已启动")
