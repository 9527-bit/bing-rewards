"""
通用工具：重试装饰器、品赞代理 API
"""

import functools
import time
import requests

from .log import logger, LogIcon, LogTag

# ===========================
# 品赞代理 API 配置（从环境变量 PINZAN_API_URL 获取，避免敏感信息泄露）
# ===========================
import os
PINZAN_API_URL = os.getenv("PINZAN_API_URL", "")

def get_pinzan_proxy():
    """从品赞 API 动态提取一个代理 IP（需配置环境变量 PINZAN_API_URL）"""
    if not PINZAN_API_URL:
        return None
    try:
        # 为了不产生过多的日志刷屏，这里不打印过多 info
        resp = requests.get(PINZAN_API_URL, timeout=10)
        proxy_text = resp.text.strip()
        # 简单校验提取出来的是否是 IP:端口
        if ":" in proxy_text and "{" not in proxy_text and "<" not in proxy_text:
            return f"http://{proxy_text}"
    except Exception as e:
        logger.warning(f"{LogIcon.WARN} {LogTag.SYSTEM} 提取品赞代理失败: {e}")
    return None

# ===========================
# 装饰器
# ===========================
def retry_decorator(retries=3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 函数 [{func.__name__}] 最终失败: {str(e)}")
                    else:
                        logger.warning(f"{LogIcon.WARN} {LogTag.SYSTEM} 函数 [{func.__name__}] 第 {attempt+1}/{retries} 次尝试失败，重试中...")
                        time.sleep(2)
            return None
        return wrapper
    return decorator
