"""
日志工具
"""
from loguru import logger
import sys
import os
from pathlib import Path

# 日志目录
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "travel-agent.log"

# 确保日志目录存在
LOG_DIR.mkdir(exist_ok=True)

# 如果是全新启动（没有运行中的进程），清空日志文件
# 通过检查是否有其他进程正在写入来判断
# 这里简单处理：每次导入时先备份并清空日志
if LOG_FILE.exists():
    # 读取现有日志行数
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 如果日志超过10000行，自动清理
        if len(lines) > 10000:
            # 备份旧日志
            from datetime import datetime
            backup_file = LOG_DIR / f"travel-agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
            with open(backup_file, "w", encoding="utf-8") as f:
                f.writelines(lines[-5000:])  # 只保留最近5000行
            # 清空当前日志
            open(LOG_FILE, "w").close()
            logger.info(f"日志已清理，备份到 {backup_file.name}")
    except Exception as e:
        print(f"日志清理失败: {e}")

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 添加文件日志 - 每天一个新文件，保留7天
logger.add(
    str(LOG_FILE),
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

__all__ = ["logger"]
