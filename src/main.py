"""
FastAPI 后端入口
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
import json

from .agent.graph import get_agent
from .utils.logger import logger

# 创建FastAPI应用
app = FastAPI(
    title="旅行规划助手 API",
    description="基于MiniMax的智能旅行规划助手",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 路由
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "旅行规划助手 API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/chat")
async def chat(request: Request):
    """普通聊天接口"""
    
    try:
        # 直接获取JSON数据
        body = await request.json()
        message = body.get("message", "")
        history = body.get("history", [])
        
        if not message:
            return JSONResponse(
                status_code=400,
                content={"error": "message不能为空"}
            )
        
        logger.info(f"收到用户消息: {message[:50]}...")
        
        # 获取Agent
        agent = get_agent()
        
        # 运行Agent
        response = agent.run(
            user_input=message,
            history=history if isinstance(history, list) else []
        )
        
        logger.info(f"Agent响应: {response[:50] if response else 'empty'}...")
        
        return JSONResponse(content={"response": response or "抱歉，未能获取有效响应"})
    
    except Exception as e:
        logger.error(f"聊天接口错误: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/tools")
async def list_tools():
    """列出可用工具"""
    from .agent.tools import get_all_tools
    
    tools = get_all_tools()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in tools
        ]
    }


# 启动日志
logger.info("旅行规划助手 API 已启动")