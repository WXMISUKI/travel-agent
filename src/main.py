"""
FastAPI 后端入口 - 智能增强版
整合时间上下文、智能计划生成器、日志审计
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
import uuid
import os
import secrets
from typing import Dict, List, Optional

from .agent.graph import get_agent
from .agent.tools import execute_tool
from .agent.time_context import get_time_context
from .utils.logger import logger
from .utils.audit_logger import get_audit_logger, EventType

app = FastAPI(title="旅行规划助手 API", version="2.0.0")

# Vercel 环境检测
is_vercel = os.environ.get("VERCEL") == "1"
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
API_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "false").strip().lower() == "true"
API_AUTH_KEY = os.getenv("API_AUTH_KEY", "").strip()
API_AUTH_HEADER = os.getenv("API_AUTH_HEADER", "x-api-key").strip().lower()

if CORS_ALLOW_ORIGINS == "*":
    _allow_origins = ["*"]
else:
    _allow_origins = [o.strip() for o in CORS_ALLOW_ORIGINS.split(",") if o.strip()]
    if not _allow_origins:
        _allow_origins = ["*"]

# 前端目录路径
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化审计日志
audit = get_audit_logger()
STREAM_DEBUG_DELAY_MS = int(os.getenv("STREAM_DEBUG_DELAY_MS", "0"))


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    """对关键接口启用 API Key 鉴权（可通过环境变量开关）"""
    protected_prefixes = ("/chat", "/audit")
    path = request.url.path

    if path.startswith(protected_prefixes):
        if not API_AUTH_ENABLED:
            return await call_next(request)

        if not API_AUTH_KEY:
            return JSONResponse(
                status_code=500,
                content={"error": "服务端未配置 API_AUTH_KEY"},
            )

        incoming_key = request.headers.get(API_AUTH_HEADER)
        if not incoming_key or not secrets.compare_digest(incoming_key, API_AUTH_KEY):
            return JSONResponse(status_code=401, content={"error": "未授权访问"})

    return await call_next(request)


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    time_ctx = get_time_context()
    logger.info(f"服务启动，当前时间: {time_ctx.get_today_formatted()}")
    logger.info(f"审计日志系统已启用")


@app.get("/")
async def root():
    if is_vercel:
        # Vercel 环境：返回前端页面
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(index_path, media_type="text/html")
    return {"name": "旅行规划助手 API", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health():
    time_ctx = get_time_context()
    return {"status": "healthy", "current_date": time_ctx.get_today_formatted()}


# ============ 新增审计接口 ============


@app.get("/audit/session/{session_id}")
async def get_session_audit(session_id: str):
    """获取会话审计信息"""
    summary = audit.get_session_summary(session_id)
    events = audit.query_events(session_id=session_id, limit=100)
    return {"summary": summary, "events": events}


@app.get("/audit/metrics")
async def get_metrics(hours: int = 24):
    """获取性能指标"""
    return audit.get_metrics_summary(hours)


@app.get("/audit/events")
async def get_events(
    session_id: str = None,
    event_type: str = None,
    tool_name: str = None,
    limit: int = 100,
):
    """查询审计事件"""
    return audit.query_events(
        session_id=session_id, event_type=event_type, tool_name=tool_name, limit=limit
    )


async def stream_response(message: str, history: list, session_id: str = None):
    """流式响应 - 智能增强版 (带审计)"""
    import time as time_module

    from .agent.graph import get_agent
    from .agent.smart_planner import get_smart_planner

    # 生成会话ID
    if not session_id:
        session_id = str(uuid.uuid4())[:8]

    # 刷新时间上下文
    time_ctx = get_time_context()
    time_ctx.refresh()

    # 获取Agent和智能计划生成器
    agent = get_agent()
    planner = get_smart_planner()

    # 启动审计轨迹
    trace = audit.start_trace(session_id, message)
    trace.intent = "unknown"

    start_time = time_module.time()
    final_response = ""
    success = True
    error_msg = ""

    try:
        def sse(data: dict) -> str:
            return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

        def sse_thinking(text: str) -> str:
            return sse({"type": "thinking_delta", "content": text})

        async def maybe_delay():
            if STREAM_DEBUG_DELAY_MS > 0:
                await asyncio.sleep(STREAM_DEBUG_DELAY_MS / 1000.0)

        yield sse({"type": "start", "session_id": session_id})

        # 思考过程
        yield sse_thinking("🧠 分析需求...")
        yield sse_thinking(f"📅 当前日期: {time_ctx.get_today_formatted()}")

        # 记录用户查询
        audit.log_user_query(session_id, message)

        # ============ 使用智能计划生成器 ============
        try:
            plan_start = time_module.time()
            plan = planner.generate_plan(message)
            plan_ms = (time_module.time() - plan_start) * 1000
            yield sse({"type": "metric", "name": "plan_ms", "value": round(plan_ms, 2)})
            trace.intent = plan.get("intent", "unknown")

            # 记录意图识别
            entities_dict = {
                k: v.value if hasattr(v, "value") else str(v)
                for k, v in plan.get("entities", {}).items()
            }
            trace.entities = entities_dict
            audit.log_intent_recognition(session_id, trace.intent, entities_dict)

        except Exception as e:
            logger.error(f"创建执行计划失败: {e}")
            error_msg = str(e)
            plan = None

        if plan and plan.get("steps"):
            # 显示意图
            intent = plan.get("intent", "unknown")
            yield sse_thinking(f"📋 意图: {intent}")

            # 显示提取的实体
            entities = plan.get("entities", {})
            entities_info = []

            for key, entity in entities.items():
                if hasattr(entity, "value"):
                    value = entity.value
                elif isinstance(entity, dict):
                    value = entity.get("value", str(entity))
                else:
                    value = str(entity)
                entities_info.append(f"{key}: {value}")

            if entities_info:
                yield sse_thinking("📍 " + ", ".join(entities_info))

            # 显示执行计划
            todo_list = []
            for s in plan["steps"]:
                todo_list.append(f"⬜ [{s['id']}] {s['tool']}: {s['purpose']}")

            yield sse_thinking("📝 执行计划:")
            yield sse({"type": "todo", "items": todo_list})
            await maybe_delay()

            # ============ 执行计划 ============
            context = {}

            for step in plan["steps"]:
                step_id = step["id"]
                tool_name = step["tool"]
                params = step["params"]
                purpose = step["purpose"]

                # 显示当前步骤
                yield sse_thinking(f"🔄 执行步骤{step_id}: {tool_name}")
                yield sse({
                    "type": "step_status",
                    "step_id": step_id,
                    "status": "running",
                    "tool": tool_name,
                    "purpose": purpose,
                })

                # 记录工具调用开始
                call_start = time_module.time()
                event_id = audit.log_tool_call(session_id, tool_name, params, step_id)

                # 替换参数占位符
                params = _resolve_params_smart(params, context)

                try:
                    result = execute_tool(tool_name, params)
                    duration_ms = (time_module.time() - call_start) * 1000

                    # 尝试解析JSON
                    try:
                        result_data = json.loads(result)
                    except:
                        result_data = {"raw": result}

                    # 记录工具结果
                    error_msg = ""
                    if "error" in result_data:
                        error_msg = result_data.get("error", "")
                        audit.log_tool_result(
                            session_id,
                            tool_name,
                            result_data,
                            duration_ms,
                            event_id,
                            error_msg,
                        )
                    else:
                        audit.log_tool_result(
                            session_id, tool_name, result_data, duration_ms, event_id
                        )
                    yield sse({"type": "metric", "name": "tool_ms", "tool": tool_name, "step_id": step_id, "value": round(duration_ms, 2)})

                    # 检查结果
                    if "error" in result_data:
                        # 失败 - 尝试修复
                        yield sse_thinking(f"⚠️ {tool_name} 提示: {error_msg[:30]}...")

                        # 尝试自动修复参数
                        fixed_params = _try_fix_tool_params(
                            tool_name, params, result_data
                        )
                        if fixed_params:
                            yield sse_thinking("🔧 尝试修复参数...")

                            # 记录降级
                            audit.log_fallback(
                                session_id, tool_name, tool_name, "参数修复重试"
                            )

                            result = execute_tool(tool_name, fixed_params)
                            duration_ms = (time_module.time() - call_start) * 1000
                            try:
                                result_data = json.loads(result)
                            except:
                                result_data = {"raw": result}

                    # 更新上下文
                    _update_context_smart(context, tool_name, result_data, entities)

                    # 检查最终结果
                    if "error" in result_data:
                        # 仍然失败，执行降级
                        yield sse_thinking(f"❌ {tool_name} 失败，执行降级...")

                        fallback_result = None
                        for fb in plan.get("fallback_plan", []):
                            fb_tool = fb["tool"]
                            fb_params = fb.get("params", {}).copy()

                            # 如果需要使用解析后的日期，进行替换
                            if fb.get("use_parsed_date") and context.get("parsed_date"):
                                for k, v in fb_params.items():
                                    if isinstance(v, str) and "{{date}}" in v:
                                        fb_params[k] = v.replace(
                                            "{{date}}", context["parsed_date"]
                                        )

                            try:
                                fb_result = execute_tool(fb_tool, fb_params)
                                fb_data = (
                                    json.loads(fb_result)
                                    if "{" in fb_result
                                    else {"raw": fb_result}
                                )
                                if "error" not in fb_data:
                                    fallback_result = fb_data
                                    yield sse_thinking("✅ 降级搜索完成")
                                    break
                            except Exception as fb_e:
                                logger.error(f"降级工具执行失败: {fb_e}")

                        if fallback_result:
                            yield sse({
                                "type": "step_status",
                                "step_id": step_id,
                                "status": "fallback_success",
                                "result": fallback_result,
                            })
                            _update_context_smart(
                                context, tool_name, fallback_result, entities
                            )
                        else:
                            yield sse({
                                "type": "step_status",
                                "step_id": step_id,
                                "status": "failed",
                                "error": result_data.get("error"),
                            })
                    else:
                        # 成功
                        yield sse_thinking(f"✅ 步骤{step_id}完成: {tool_name}")
                        yield sse({
                            "type": "step_status",
                            "step_id": step_id,
                            "status": "completed",
                            "result": result_data,
                        })

                except Exception as e:
                    logger.error(f"步骤执行异常: {e}")
                    yield sse_thinking(f"❌ 异常: {str(e)}")
                    yield sse({
                        "type": "step_status",
                        "step_id": step_id,
                        "status": "error",
                        "error": str(e),
                    })

                await maybe_delay()

            # ============ 生成最终回复 ============
            yield sse_thinking("📝 生成回复...")

            # 使用 Agent 异步流式生成回复
            llm_start = time_module.time()
            response_payload = {
                "step_results": {},
                "context": context,
                "intent": plan.get("intent"),
                "entities": entities,
            }
            response_chunks = []
            async for chunk in agent.astream_response_from_smart_plan(
                message,
                plan,
                response_payload,
            ):
                response_chunks.append(chunk)
                yield sse({"type": "content", "content": chunk})
                await asyncio.sleep(0)
            response = "".join(response_chunks)
            llm_ms = (time_module.time() - llm_start) * 1000
            yield sse({"type": "metric", "name": "llm_ms", "value": round(llm_ms, 2)})

            # 记录响应
            final_response = response
            audit.log_response(session_id, response, success=True)

            yield sse({"type": "done", "session_id": session_id})
        else:
            # 执行计划创建失败，使用传统流程
            yield sse_thinking("🧠 使用传统模式...")

            intent = agent._parse_intent(message)
            tools = intent.get("needed_tools", [])

            dest = intent.get("destination") or intent.get("city") or ""
            origin = intent.get("origin") or ""
            date = intent.get("date") or "近期"

            results = {}

            if "get_weather" in tools and dest:
                yield sse_thinking(f"🌤️ 查询天气: {dest}")
                results["天气"] = agent._call_with_fallback(
                    "get_weather", {"city": dest}, lambda: agent._baidu_weather(dest)
                )

            if "get_train_tickets" in tools and origin and dest:
                yield sse_thinking("🚄 查询火车票...")
                results["火车票"] = agent._call_with_fallback(
                    "get_train_tickets",
                    {"date": date, "from_station": origin, "to_station": dest},
                    lambda: agent._baidu_transport(origin, dest),
                )

            if "search_attractions" in tools and dest:
                yield sse_thinking(f"🎯 查询景点: {dest}")
                results["景点"] = agent._call_with_fallback(
                    "search_attractions",
                    {"city": dest, "keyword": "景点"},
                    lambda: agent._baidu_attractions(dest),
                )

            yield sse_thinking("📝 生成回复...")

            response_chunks = []
            for chunk in agent.stream_response(message, intent, results):
                response_chunks.append(chunk)
                yield sse({"type": "content", "content": chunk})
            response = "".join(response_chunks)

            # 记录响应
            final_response = response
            audit.log_response(session_id, response, success=True)

            yield sse({"type": "done", "session_id": session_id})

    except Exception as e:
        logger.error(f"流式错误: {e}")
        error_msg = str(e)
        import traceback

        traceback.print_exc()
        yield sse({"type": "error", "content": str(e)})

        # 记录错误
        success = False
        audit.log_response(session_id, f"错误: {error_msg}", success=False)

    finally:
        # 结束审计轨迹
        total_duration = (time_module.time() - start_time) * 1000
        try:
            yield sse({"type": "metric", "name": "total_ms", "value": round(total_duration, 2)})
        except Exception:
            pass
        audit.end_trace(
            trace.trace_id,
            success=success,
            error_message=error_msg,
            final_response=final_response,
        )


def _resolve_params_smart(params: Dict, context: Dict) -> Dict:
    """解析参数占位符 - 修复版"""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
            key = v[2:-2]  # 例如 "parse_date.result"

            # 尝试多种可能的键名
            # 1. parse_date.result -> parsed_date
            if key == "parse_date.result":
                resolved[k] = context.get("parsed_date", v)
            # 2. origin_station -> origin_station
            elif key == "origin_station":
                resolved[k] = context.get("origin_station", v)
            # 3. destination_station -> destination_station
            elif key == "destination_station":
                resolved[k] = context.get("destination_station", v)
            # 4. 其他情况直接获取
            else:
                resolved[k] = context.get(key, v)
        else:
            resolved[k] = v

    # 如果仍然是占位符，尝试从 entities 获取默认值
    for k, v in resolved.items():
        if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
            # 对于日期，如果没有解析结果，使用今天
            if k == "date":
                from datetime import datetime

                resolved[k] = datetime.now().strftime("%Y-%m-%d")

    return resolved


def _try_fix_tool_params(
    tool_name: str, params: Dict, error_result: Dict
) -> Optional[Dict]:
    """尝试修复工具参数"""
    import re

    error_msg = error_result.get("error", "")
    fixed = params.copy()

    if tool_name == "get_train_tickets":
        # 尝试从错误信息提取有效站名
        station_match = re.search(r"([^\s,，、。]{2,6}站)", error_msg)
        if station_match:
            return fixed

        # 尝试去掉县等
        for key in ["from_station", "to_station"]:
            if key in fixed:
                station = str(fixed[key])
                if "县" in station:
                    fixed[key] = station.replace("县", "市")
                    return fixed

    return None


def _update_context_smart(
    context: Dict, tool_name: str, result_data: Dict, entities: Dict
):
    """更新执行上下文"""
    if tool_name == "get_station_by_city":
        city = result_data.get("city", "")
        stations = result_data.get("stations", [])
        recommended = result_data.get("recommended", "")

        # 判断是出发地还是目的地
        origin_city = ""
        dest_city = ""

        if isinstance(entities.get("origin"), dict):
            origin_city = entities["origin"].get("value", "")
        elif hasattr(entities.get("origin"), "value"):
            origin_city = entities["origin"].value

        if isinstance(entities.get("destination"), dict):
            dest_city = entities["destination"].get("value", "")
        elif hasattr(entities.get("destination"), "value"):
            dest_city = entities["destination"].value

        if city == origin_city:
            context["origin_station"] = recommended
            context["origin_stations"] = (
                [s.get("name") for s in stations] if stations else []
            )
        elif city == dest_city:
            context["destination_station"] = recommended
            context["destination_stations"] = (
                [s.get("name") for s in stations] if stations else []
            )

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


# 保留旧版本的函数用于兼容（如有需要）
async def stream_response_old(message: str, history: list):
    """已废弃的旧版本流式响应函数"""
    pass


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
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
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

    return {
        "tools": [
            {"name": k, "description": v["description"]}
            for k, v in AVAILABLE_TOOLS.items()
        ]
    }


# ============ LangGraph 工作流 API ============


@app.post("/chat/workflow")
async def chat_workflow(request: Request):
    """使用 LangGraph 工作流的聊天接口"""
    try:
        body = await request.json()
        msg = body.get("message", "")
        session_id = body.get("session_id")

        if not msg:
            return JSONResponse(status_code=400, content={"error": "message不能为空"})

        logger.info(f"[Workflow] 请求: {msg[:50]}...")

        # 刷新时间上下文
        time_ctx = get_time_context()
        time_ctx.refresh()

        # 导入并运行工作流
        from .agent.workflow import run_agent

        result = run_agent(msg, session_id)

        return JSONResponse(
            content={
                "success": result.get("success", False),
                "response": result.get("response", ""),
                "intent": result.get("intent"),
                "entities": result.get("entities", {}),
                "tool_results": result.get("tool_results", {}),
                "fallback_used": result.get("fallback_used", False),
            }
        )

    except Exception as e:
        logger.error(f"工作流错误: {e}")
        import traceback

        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


logger.info("API已启动")
