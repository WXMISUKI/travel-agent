"""
日志工具
"""
from loguru import logger
import sys

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 添加文件日志
logger.add("logs/travel-agent.log", rotation="10 MB", level="INFO")

__all__ = ["logger"]
