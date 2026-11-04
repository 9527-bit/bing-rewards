"""
日志配置、日志标签/图标/缩进常量、虚拟显示器支持检测
"""

import os
import sys
from loguru import logger

# ===========================
# 日志配置（控制台实时输出 + 本地文件持久化）
# ===========================
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(_PROJECT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()

# 1. 控制台终端实时输出
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> <level>| {level: <7} |</level> <level>{message}</level>",
    level="INFO"
)

# 2. 每次运行生成独立的日志文件（按时间戳命名，自动保留最近 30 天）
logger.add(
    os.path.join(LOG_DIR, "run_{time:YYYY-MM-DD_HH-mm-ss}.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {message}",
    level="INFO",
    encoding="utf-8",
    retention="30 days"
)

# 3. 始终指向最近一次执行的最新日志文件
logger.add(
    os.path.join(LOG_DIR, "latest.log"),
    mode="w",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {message}",
    level="INFO",
    encoding="utf-8"
)

# ===========================
# 日志规范化常量
# ===========================
class LogTag:
    """日志模块标签常量"""
    SYSTEM   = "[System]"
    COOKIE   = "[Cookie]"
    LOGIN    = "[Login]"
    ACCOUNT  = "[Account]"
    POINTS   = "[Points]"
    SEARCH   = "[Search]"
    ACTIVITY = "[Activity]"
    READ     = "[Read]"
    NOTIFY   = "[Notify]"
    QINGLONG = "[QL]"

class LogIcon:
    """日志状态图标常量"""
    START   = "🚀"
    SUCCESS = "✅"
    FAIL    = "❌"
    WARN    = "⚠️"
    INFO    = "📋"
    DATA    = "📊"
    POINTS  = "💰"
    ITEM    = "👉"
    KEY     = "🔑"
    COOKIE  = "🍪"
    CLEAN   = "🧹"
    BELL    = "🔔"
    SEARCH  = "🔍"
    READ    = "📖"
    PC      = "💻"
    MOBILE  = "📱"

class LogIndent:
    """日志缩进常量"""
    L1 = ""
    L2 = "   ├── "
    L2_END = "   └── "

# ===========================
# 虚拟显示器支持（Docker/Linux 环境必需）
# ===========================
try:
    from pyvirtualdisplay import Display
    HAS_DISPLAY = True
except ImportError:
    Display = None
    HAS_DISPLAY = False
    logger.warning(f"{LogIcon.WARN} {LogTag.SYSTEM} 未安装 pyvirtualdisplay，将尝试普通模式")
