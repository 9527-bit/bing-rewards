"""
日志配置、日志标签/图标/缩进常量、虚拟显示器支持检测
"""

import sys
from loguru import logger

# ===========================
# 日志配置
# ===========================
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> <level>| {level: <7} |</level> <level>{message}</level>",
    level="INFO"
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
