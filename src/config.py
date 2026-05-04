"""
配置管理模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 豆包（火山引擎 Ark）配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ark").strip().lower()
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_MODEL", "")
ARK_API_KEY = os.getenv("ARK_API_KEY", "")

# 百度搜索API
BAIDU_SEARCH_API_KEY = os.getenv("BAIDU_SEARCH_API_KEY", "")

# 12306 MCP服务
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8000")

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 缓存配置
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
