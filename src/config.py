"""
配置管理模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# MiniMax配置
ORCH_API_BASE = os.getenv("ORCH_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
ORCH_MODEL = os.getenv("ORCH_MODEL", "MiniMax/MiniMax-M2.5")
ORCH_API_KEY = os.getenv("ORCH_API_KEY", "")

# 百度搜索API
BAIDU_SEARCH_API_KEY = os.getenv("BAIDU_SEARCH_API_KEY", "")

# 12306 MCP服务
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8000")

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 缓存配置
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
