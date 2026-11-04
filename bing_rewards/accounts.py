"""
账号配置文件读取、Cookie 持久化读写
"""

import os
import json

from .log import logger, LogIcon, LogTag

# ===========================
# 账号及凭证读取 (本地 JSON 版)
# ===========================

# 文件路径：相对于包的父目录（即项目根目录）
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_FILE = os.path.join(_PROJECT_DIR, "bing_accounts.json")
COOKIES_FILE = os.path.join(_PROJECT_DIR, "bing_cookies.json")

def get_accounts():
    """从同目录下 bing_accounts.json 读取多账号配置"""
    if not os.path.exists(ACCOUNTS_FILE):
        logger.error(f"{LogIcon.FAIL} {LogTag.ACCOUNT} 未找到账号文件: {ACCOUNTS_FILE}")
        logger.info(f"{LogIcon.INFO} {LogTag.ACCOUNT} 请创建 {ACCOUNTS_FILE}，格式如下:\n[\n  {{\"username\": \"xxx@outlook.com\", \"password\": \"xxx\"}}\n]")
        return []
    
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        accounts = []
        for i, acc in enumerate(data):
            if acc.get("username") and acc.get("password"):
                accounts.append({
                    "index": i + 1,
                    "username": acc["username"],
                    "password": acc["password"],
                    # 使用 username 作为 key 保存对应 cookie
                    "cookie_key": acc["username"] 
                })
        return accounts
    except Exception as e:
        logger.error(f"{LogIcon.FAIL} {LogTag.ACCOUNT} 读取账号文件异常: {e}")
        return []

def get_cookie_from_local(cookie_key):
    """从本地 bing_cookies.json 中读取指定的 Cookie/Token"""
    if not os.path.exists(COOKIES_FILE):
        return None
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get(cookie_key)
        if val:
            logger.info(f"{LogTag.COOKIE} 从本地读取缓存数据 [{cookie_key[:10]}...]")
        return val
    except Exception as e:
        logger.error(f"{LogIcon.FAIL} {LogTag.COOKIE} 读取本地凭证失败: {e}")
    return None

def save_cookie_to_local(cookie_key, cookie_str):
    """保存 Cookie/Token 到本地 bing_cookies.json"""
    data = {}
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
            
    data[cookie_key] = cookie_str
    
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        if "TOKEN" in cookie_key.upper() or "REFRESH" in cookie_key.upper():
            logger.success(f"{LogIcon.SUCCESS} {LogTag.COOKIE} Token 凭证已持久化到本地")
        else:
            logger.success(f"{LogIcon.SUCCESS} {LogTag.COOKIE} Cookie 缓存已持久化到本地")
            
        return True
    except Exception as e:
        logger.error(f"{LogIcon.FAIL} {LogTag.COOKIE} 保存本地凭证异常: {e}")
    return False
