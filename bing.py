"""
cron: 10 0,8,16 * * *
new Env("Bing Rewards 自动化(密码登录版)")
From:yaohuo28507
"""

import os
import json
import random
import time
import functools
import sys
import re
import requests
import secrets
from loguru import logger

# ===========================
# 脚本版本号
# ===========================
VERSION = "v1.0.1" #20260603

# ===========================
# 品赞代理 API 配置（从环境变量 PINZAN_API_URL 获取，避免敏感信息泄露）
# ===========================
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

# 尝试引入 pyvirtualdisplay（Docker/Linux 环境必需）
try:
    from pyvirtualdisplay import Display
    HAS_DISPLAY = True
except ImportError:
    logger.warning(f"{LogIcon.WARN} {LogTag.SYSTEM} 未安装 pyvirtualdisplay，将尝试普通模式")
    HAS_DISPLAY = False

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

# ===========================
# 环境变量读取
# ===========================
# 清理 DISPLAY 环境变量（避免干扰虚拟显示器）
os.environ.pop("DISPLAY", None)

# ===========================
# 账号及凭证读取 (本地 JSON 版)
# ===========================

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "bing_accounts.json")
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "bing_cookies.json")

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


# ===========================
# 热搜词管理
# ===========================
class HotWordsManager:
    """热搜词管理器，从多个公开免费 API 获取今日热点作为搜索词以防止风控"""
    def __init__(self):
        self.hot_words = self._fetch_hot_words()

    def _fetch_hot_words(self, max_count: int = 40) -> list:
        apis = [
            ("https://dailyapi.eray.cc/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq-news", "netease-news", "zhihu"]),
            ("https://cnxiaobai.com/DailyHotApi/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq-news", "netease-news", "zhihu"]),
            ("https://hotapi.nntool.cc/", ["weibo", "douyin", "baidu", "toutiao", "thepaper", "qq-news", "netease-news", "zhihu"])
        ]
        
        random.shuffle(apis)
        
        for base_url, sources in apis:
            sources_shuffled = sources[:]
            random.shuffle(sources_shuffled)
            
            for source in sources_shuffled:
                api_url = base_url + source
                try:
                    resp = requests.get(api_url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict) and 'data' in data and data['data']:
                            all_titles = [item.get('title') for item in data['data'] if item.get('title')]
                            if all_titles:
                                logger.info(f"{LogIcon.DATA} {LogTag.SEARCH} 成功获取热搜词 {len(all_titles)} 条，来源: {api_url}")
                                random.shuffle(all_titles)
                                return all_titles[:max_count]
                except Exception:
                    continue

        logger.warning(f"{LogIcon.WARN} {LogTag.SEARCH} 所有热搜 API 请求失败，使用本地兜底词库。")
        default_words = [
            "盛年不重来，一日难再晨", "千里之行，始于足下", "少年易学老难成，一寸光阴不可轻",
            "敏而好学，不耻下问", "海内存知已，天涯若比邻", "三人行，必有我师焉",
            "莫愁前路无知已，天下谁人不识君", "人生贵相知，何用金与钱", "天生我材必有用",
            "海纳百川有容乃大；壁立千仞无欲则刚", "穷则独善其身，达则兼济天下", "读书破万卷，下笔如有神",
            "微软必应积分活动", "如何获取微软 Reward", "今天的天气", "中国历史朝代",
            "人工智能的发展", "Windows 11 更新", "唐诗三百首", "宋词精选"
        ]
        random.shuffle(default_words)
        return default_words[:max_count]

    def get_random_word(self) -> str:
        if not self.hot_words:
            self.hot_words = self._fetch_hot_words()
        # 弹出一个，避免本轮搜索到完全相同的词
        return self.hot_words.pop() if self.hot_words else "微软必应积分"


# 准备全局热搜词管理器
hot_words_manager = HotWordsManager()


# ===========================
# URL 常量
# ===========================
REWARDS_URL = "https://rewards.bing.com/dashboard"
REWARDS_SIGNIN_URL = "https://rewards.bing.com/Signin/"
REWARDS_EARN_URL = "https://rewards.bing.com/earn"
BING_URL = "https://www.bing.com/"
SEARCH_HOME_WWW_URL = "https://www.bing.com/?form=ML2PCO"
SEARCH_HOME_CN_URL = "https://cn.bing.com/?form=ML2PCO"
SEARCH_REQUEST_URL = "https://cn.bing.com/search"


# OAuth 令牌相关
OAUTH_CLIENT_ID = "0000000040170455"
OAUTH_REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"
OAUTH_SCOPE = "service::prod.rewardsplatform.microsoft.com::MBI_SSL"
OAUTH_AUTHORIZE_URL = (
    f"https://login.live.com/oauth20_authorize.srf"
    f"?client_id={OAUTH_CLIENT_ID}"
    f"&scope={OAUTH_SCOPE}"
    f"&response_type=code"
    f"&redirect_uri={OAUTH_REDIRECT_URI}"
)
OAUTH_TOKEN_URL = "https://login.live.com/oauth20_token.srf"

# Next.js Server Action ID 匹配正则（用于从 JS Chunks 中提取 next-action ID）
# 匹配特征："<hex_id>",x.callServer  其中 x 为任意变量名
RE_NEXT_ACTION = re.compile(r'"([0-9a-f]{32,})",[a-zA-Z_$][a-zA-Z0-9_$]*\.callServer')


# ===========================
# 核心类：Bing Rewards 浏览器
# ===========================
class BingRewardsBrowser:
    def __init__(self):
        self.display = None
        self.browser = None
        self.page = None
        self._last_rsc_data = ""  # 缓存 /earn 页面 RSC 数据，供 quest 解析复用
        logger.info(f"{LogIcon.START} 启动 Bing Rewards 自动化脚本 (版本: {VERSION})...")

        # 1. 启动虚拟显示器
        if HAS_DISPLAY:
            try:
                self.display = Display(visible=0, size=(1920, 1080))
                self.display.start()
                logger.info(f"{LogTag.SYSTEM} 虚拟显示器启动成功")
            except Exception as e:
                logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 虚拟显示器启动失败: {e}")

        # 2. 配置 Chromium
        from DrissionPage import ChromiumOptions, Chromium

        co = ChromiumOptions()
        co.headless(False)  # pyvirtualdisplay 模式下必须为 False
        co.incognito(True)
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        co.set_argument("--disable-dev-shm-usage")
        co.set_argument("--window-size=1920,1080")
        co.set_argument("--mute-audio")
        co.set_argument("--lang=zh-CN")
        co.set_argument("--accept-lang=zh-CN,zh;q=0.9")
        # 强制底层首选项为中文
        co.set_pref("intl.accept_languages", "zh-CN,zh")
        # 禁用密码管理器弹窗
        co.set_argument("--disable-password-manager-reauthentication")

        # 自动路径查找（Linux）
        if os.path.exists("/usr/bin/chromium"):
            co.set_browser_path("/usr/bin/chromium")
        elif os.path.exists("/usr/bin/chromium-browser"):
            co.set_browser_path("/usr/bin/chromium-browser")
        elif os.path.exists("/usr/bin/google-chrome"):
            co.set_browser_path("/usr/bin/google-chrome")

        try:
            self.browser = Chromium(co)
            self.page = self.browser.latest_tab
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 浏览器启动失败: {e}")
            if self.display:
                self.display.stop()
            sys.exit(1)

        logger.info(f"{LogTag.SYSTEM} 浏览器启动成功，UA: {self.page.user_agent[:60]}...")

    # ===========================
    # Cookie 管理
    # ===========================
    def _get_cookie_string(self):
        """从浏览器获取 Cookie 字符串（JSON 格式）"""
        try:
            browser_cookies = self.page.cookies()
            key_cookies = []
            for c in browser_cookies:
                domain = c.get("domain", "")
                if "bing.com" in domain or "live.com" in domain or "microsoft.com" in domain:
                    key_cookies.append({
                        "name": c.get("name"),
                        "value": c.get("value"),
                        "domain": domain,
                        "path": c.get("path", "/")
                    })
            return json.dumps(key_cookies)
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.COOKIE} 获取字符串失败: {e}")
            return None

    def _get_cookie_header(self):
        """从浏览器 Cookie 构建 HTTP 请求用的 Cookie 字符串"""
        try:
            browser_cookies = self.page.cookies()
            parts = []
            for c in browser_cookies:
                name = c.get("name")
                value = c.get("value")
                if name and value:
                    parts.append(f"{name}={value}")
            return "; ".join(parts)
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.COOKIE} 构建 header 失败: {e}")
            return ""

    def _inject_cookies(self, cookie_str):
        """注入 Cookie 到浏览器"""
        try:
            cookies = json.loads(cookie_str)
            if not cookies:
                return False
            for c in cookies:
                try:
                    self.page.set.cookies(c)
                except Exception as e:
                    logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} 注入 [{c.get('name')}] 失败: {e}")
            return True
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.COOKIE} 注入异常: {e}")
            return False

    def _fetch_next_action_id(self):
            """动态从页面的 JS Chunks 中抓取最新的 next-action ID"""
            try:
                # 1. 获取页面上所有的 script 标签
                scripts = self.page.eles('tag:script')
                js_urls = []
                for s in scripts:
                    src = s.attr('src')
                    # 寻找包含 chunks 的脚本，通常 Action ID 就在这些文件里
                    if src and '/_next/static/chunks/' in src:
                        js_urls.append(src)
                
                # 2. 逆序遍历脚本（通常业务逻辑在后面的 chunk 中）
                for url in reversed(js_urls):
                    if not url.startswith('http'):
                        url = f"https://rewards.bing.com{url}"
                    
                    # 请求 JS 内容
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        # 匹配截图中的特征： "ID",o.callServer
                        match = RE_NEXT_ACTION.search(resp.text)
                        if match:
                            action_id = match.group(1)
                            logger.info(f"{LogIcon.KEY} [System] 动态抓取到 next-action: {action_id}")
                            return action_id
                
                # 兜底：如果 JS 里没搜到，尝试在主页 HTML 里搜（有时会内联）
                match = RE_NEXT_ACTION.search(self.page.html)
                if match:
                    return match.group(1)

            except Exception as e:
                logger.error(f"抓取 next-action 失败: {e}")
            
            # 如果实在抓不到，返回你截图里那个作为最后的兜底
            return "00cf5ba7699f0e920ffcff223f9e48fea78fd49784"

    # ===========================
    # Microsoft 登录流程
    # ===========================
    def _dismiss_messages(self):
        """尝试关闭各种弹窗和消息"""
        # Microsoft 登录过程中常见的弹窗按钮 ID 列表
        button_selectors = [
            "#idSIButton9",          # "下一步" / "登录" / "是，保持登录"
            "#iShowSkip",            # "跳过"
            "#iNext",                # "下一步"
            "#iLooksGood",           # "看起来不错"
            "#iLandingViewAction",   # 着陆页操作
            "#idBtn_Back",           # "否" / "返回"
            "#acceptButton",         # 接受按钮
            "#wcpConsentBannerCtrl button:nth-child(2)",  # Cookie 横幅
        ]
        for sel in button_selectors:
            try:
                # 将 timeout=1 改为 timeout=0.1，避免 8个没有的按钮造成每次循环至少 8s 的阻塞
                btn = self.page.ele(sel, timeout=0.1)
                if btn:
                    btn.click()
                    time.sleep(1)
                    return True
            except:
                continue
        return False

    def _wait_for_login_redirect(self, timeout=30):
        """等待登录后跳转回 bing.com 或 rewards.bing.com"""
        for i in range(timeout):
            time.sleep(1)
            current_url = self.page.url or ""
            # 已经到达 Rewards 页面或 Bing 首页
            if ("rewards.bing.com" in current_url and "Signin" not in current_url) or \
               ("bing.com" in current_url and "login.live.com" not in current_url and "microsoftonline.com" not in current_url):
                return True
            
            # 快速异常状态检测（如拦截、密码错误、锁定等），及时止损
            page_text = self.page.html or ""
            error_keywords = ["已被锁定", "密码不正确", "存在异常活动", "帮助我们保护", "登录被阻止", "help us protect", "locked", "action required"]
            for kw in error_keywords:
                if kw in page_text.lower() or kw in page_text:
                    logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 页面存在异常/风控提示: '{kw}'，停止等待")
                    return False
            
            # 处理中间弹窗
            self._dismiss_messages()
        return False

    @retry_decorator(retries=2)
    def login(self, username, password, account_index=1):
        """使用账号密码登录 Microsoft Rewards"""
        logger.info(f"{LogIcon.KEY} {LogTag.LOGIN} 账号{account_index} 开始登录流程...")
        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 邮箱: {username[:3]}***{username[-10:]}")

        try:
            # === 第一步：访问 Bing 首页触发登录 ===
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 正在访问 Bing 首页准备登录...")
            self.page.get(BING_URL)
            time.sleep(random.uniform(2, 4))

            # 再刷新一次确保页面完全加载（兼容可能带出的 SSO 重定向状态）
            self.page.refresh()
            time.sleep(random.uniform(2, 4))

            # 寻找并点击首页的登录按钮
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 寻找首页登录入口...")
            login_btn = None
            try:
                # 检查页面右上角是否显示登录按钮（id="id_l" 等待时间从2适当调整，增加兼容性）
                login_btn = self.page.ele('#id_l', timeout=2)
                if login_btn:
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 尝试点击右上角入口...")
                    login_btn.click()
                    time.sleep(2) # 给白色卡片弹出的时间
                    
                    # 检查是否弹出了包含“退出”的卡片（半登录态）
                    logout_btn = self.page.ele('tag:a@@text():退出', timeout=2)
                    if logout_btn:
                        logger.warning(f"{LogIndent.L2}{LogTag.LOGIN} 检测到失效的半登录状态，正在点击退出重置环境...")
                        logout_btn.click()
                        time.sleep(random.uniform(3, 5))
                        
                        # ==========================================
                        # 核心修改：重新定向到 Bing 首页，彻底重置页面状态
                        # ==========================================
                        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 退出成功，重新定向到首页以刷新状态...")
                        self.page.get(BING_URL)  # 这里使用了脚本开头定义的 BING_URL 常量
                        time.sleep(random.uniform(3, 5))
                        
                        # 重新寻找干净的登录按钮并点击
                        login_btn = self.page.ele('#id_l', timeout=3)
                        if login_btn:
                            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 再次点击右上角登录按钮，进入账号密码流程...")
                            login_btn.click()
                            
                    time.sleep(random.uniform(5, 7))
            except Exception as e:
                pass
            

            # 等待 Microsoft 登录页面加载
            # 可能是在当前页弹出 iframe，也可能重定向到了 login.live.com
            for wait in range(15):
                current_url = self.page.url or ""
                if "login.live.com" in current_url or "login.microsoftonline.com" in current_url:
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已到达 Microsoft 登录页")
                    break
                
                # 检查 iframe 内或当前 DOM 中是否已经出现输入框
                if self.page.ele("#usernameEntry", timeout=0.1) or self.page.ele("#i0116", timeout=0.1):
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 登录弹窗/元素已出现")
                    break
                time.sleep(1)
            else:
                # 可能已经登录了
                page_html = self.page.html or ""
                if "id_n" in page_html or "id_p" in page_html or "退出登录" in page_html:
                    logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 已处于登录状态")
                    return True
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 未正常展开登录页面，当前: {self.page.url}")
                return False

            time.sleep(2)

            # === 第二步：输入邮箱 ===
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 输入邮箱...")
            # 新版 Fluent UI 用 #usernameEntry，旧版用 #i0116
            email_input = self.page.ele("#usernameEntry", timeout=10)
            if not email_input:
                email_input = self.page.ele("#i0116", timeout=5)
            if not email_input:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 未找到邮箱输入框")
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 当前URL: {self.page.url}")
                return False

            email_input.clear()
            time.sleep(0.5)
            email_input.input(username)
            time.sleep(1)
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 邮箱已输入")

            # 点击"下一步"按钮
            if not self._click_submit_button("下一步"):
                return False
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已提交邮箱，等待密码页...")
            time.sleep(3)

            # === 第三步：处理可能的中间页面 ===
            # 有些账号会弹出"选择账号类型"或恢复邮箱验证
            self._handle_intermediate_pages()

            # === 第四步：输入密码 ===
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 输入密码...")
            # 等待真正的密码输入框出现（避免把“使用密码”选项误判为输入框）
            password_input = self._wait_for_password_input(timeout=20)
            if not password_input:
                # 可能还在邮箱页面，再次尝试处理中间页面
                logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 未找到密码框，尝试处理中间页面...")
                self._handle_intermediate_pages()
                password_input = self._find_password_input(timeout=8)
            if not password_input:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 未找到密码输入框")
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 当前URL: {self.page.url}")
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 页面标题: {self.page.title}")
                return False

            password_input.clear()
            time.sleep(0.5)
            # 直接整体输入密码
            password_input.input(password)
            time.sleep(1)

            # 点击"登录"按钮
            if not self._click_submit_button("登录"):
                return False
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已提交密码，等待登录结果...")
            time.sleep(3)

            # === 第五步：处理"保持登录"弹窗 ===
            self._handle_stay_signed_in()

            # === 第六步：等待跳转回 Rewards 页面 ===
            if self._wait_for_login_redirect(timeout=20):
                logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 登录成功!")
                return True
            else:
                # 最后再检测一次当前页面
                current_url = self.page.url or ""
                if "rewards.bing.com" in current_url:
                    logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 登录成功!")
                    return True
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 登录超时，当前URL: {current_url}")
                return False

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 登录异常: {e}")
            return False

    def _click_submit_button(self, action_name="提交"):
        """点击提交/下一步/登录按钮，兼容新旧两版 Microsoft 登录页"""
        # 方案1：新版 Fluent UI 的 data-testid="primaryButton"
        btn = self.page.ele('css:button[data-testid="primaryButton"]', timeout=3)
        if btn:
            btn.click()
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击「{action_name}」(Fluent UI)")
            return True

        # 方案2：旧版 #idSIButton9
        btn = self.page.ele("#idSIButton9", timeout=3)
        if btn:
            btn.click()
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击「{action_name}」(Classic)")
            return True

        # 方案3：通过文本查找按钮
        for text in ["下一步", "登录", "Next", "Sign in"]:
            btn = self.page.ele(f'tag:button@@text()={text}', timeout=1)
            if btn:
                btn.click()
                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击「{text}」")
                return True

        # 方案4：通过 JS 直接点击
        try:
            result = self.page.run_js("""
                // 新版 Fluent UI
                var btn = document.querySelector('button[data-testid="primaryButton"]');
                if (btn) { btn.click(); return 'fluent'; }
                // 旧版
                btn = document.getElementById('idSIButton9');
                if (btn) { btn.click(); return 'classic'; }
                // 所有 submit 按钮
                var submits = document.querySelectorAll('input[type="submit"], button[type="submit"]');
                if (submits.length > 0) { submits[0].click(); return 'submit'; }
                return null;
            """)
            if result:
                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已通过JS点击「{action_name}」({result})")
                return True
        except:
            pass

        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 未找到「{action_name}」按钮")
        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 当前URL: {self.page.url}")
        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 页面标题: {self.page.title}")
        return False

    def _find_password_input(self, timeout=1):
        """查找真正可输入的密码输入框"""
        selectors = [
            'css:input#i0118',
            'css:input[name="i0118"]',
            'css:input[name="passwd"]',
            'css:input#passwordInput',
            'css:input[name="passwordInput"]',
            'css:input#password',
            'css:input[name="password"]',
            'css:input#passwordEntry[type="password"]',
            'css:input[name="passwordEntry"]',
            'css:input[type="password"]',
        ]
        for sel in selectors:
            try:
                password_input = self.page.ele(sel, timeout=timeout)
                if password_input:
                    return password_input
            except:
                continue
        return None

    def _wait_for_password_input(self, timeout=20):
        """等待密码输入框出现，期间重试处理中间页"""
        end_time = time.time() + timeout
        last_handle_time = 0
        while time.time() < end_time:
            password_input = self._find_password_input(timeout=0.5)
            if password_input:
                return password_input

            now = time.time()
            if now - last_handle_time >= 2:
                self._handle_intermediate_pages()
                last_handle_time = now
            time.sleep(0.4)
        return None

    def _handle_intermediate_pages(self):
        """处理登录过程中可能出现的中间页面（验证方式选择、账号类型选择等）"""
        time.sleep(1)

        # === 场景1：验证方式选择页面（新版 Fluent UI） ===
        # 输入邮箱后，Microsoft 可能显示多种验证方式：
        # - 使用 Microsoft Authenticator
        # - 使用密码
        # - 使用安全密钥
        # 需要点击"使用密码"选项
        try:
            # 已经在密码输入页则直接返回
            if self._find_password_input(timeout=0.3):
                return

            # 某些页面先展示"显示更多选项"，需要先展开
            for text in ["显示更多选项", "Show more options"]:
                show_more = self.page.ele(f'tag:button@@text():{text}', timeout=0.8)
                if show_more:
                    show_more.click()
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击「{text}」")
                    time.sleep(1)
                    break

            page_text = self.page.html or ""
            page_text_lower = page_text.lower()
            # 检测是否在验证方式选择页面
            if (
                "验证" in page_text
                or "使用另一种方式登录" in page_text
                or "verify" in page_text_lower
                or "credential" in page_text_lower
                or "show more options" in page_text_lower
                or "passwordEntry" in page_text
            ):
                # 方式1：通过 JS 精确查找并点击密码选项（最快且无多次超时阻塞叠加）
                try:
                    result = self.page.run_js("""
                        var candidates = document.querySelectorAll(
                            '[data-testid="credential-picker-password"], [data-testid="passwordEntry"], #idA_PWD_SwitchToPassword, button, a, div[role="button"], span[role="button"], span[role="button"][tabindex], div[role="button"][tabindex], [tabindex="0"], div.row'
                        );
                        for (var el of candidates) {
                            var text = (el.textContent || '').trim();
                            var lower = text.toLowerCase();
                            if (!text) continue;
                            if (text.includes('使用密码') || lower.includes('use a password') || lower.includes('use password') || lower === 'password') {
                                el.scrollIntoView({block: 'center'});
                                el.click();
                                return text.substring(0, 40);
                            }
                        }
                        return null;
                    """)
                    if result:
                        time.sleep(1)
                        if self._find_password_input(timeout=3):
                            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已通过JS选择「使用密码」验证方式: {result.strip()}")
                            return
                        logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} JS 点击后未进入密码页，继续后续流程...")
                except:
                    pass

                # 方式2：通过更精确的选择器批量查找
                exact_selector = 'css:[data-testid="credential-picker-password"], [data-testid="passwordEntry"], #idA_PWD_SwitchToPassword'
                pwd_option = self.page.ele(exact_selector, timeout=1)
                if pwd_option:
                    pwd_option.click()
                    time.sleep(1)
                    if self._find_password_input(timeout=3):
                        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已选择「使用密码」验证方式 (选择器命中)")
                        return
                    logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 点击选择器后未进入密码页，继续尝试...")

                # 方式3：缩小超时的按文本查找（防止阻塞过长）
                for text in ["使用密码", "Use a password", "Use password", "Password"]:
                    for tag in ["button", "a", "div", "span"]:
                        pwd_option = self.page.ele(f'tag:{tag}@@text():{text}', timeout=0.1)
                        if pwd_option:
                            pwd_option.click()
                            time.sleep(1)
                            if self._find_password_input(timeout=3):
                                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已选择「{text}」验证方式")
                                return
        except:
            pass

        # === 场景2：选择账号类型（个人/工作） ===
        try:
            work_account = self.page.ele("#aadTile", timeout=2)
            if work_account:
                personal = self.page.ele("#msaTile", timeout=2)
                if personal:
                    personal.click()
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 选择「个人账号」")
                    time.sleep(2)
                    return
        except:
            pass

        # === 场景3：恢复邮箱检查 / 切换到密码登录（旧版） ===
        try:
            skip_selectors = [
                "#idA_PWD_SwitchToPassword",  # 旧版：切换到密码登录
                "#iShowSkip",                  # 跳过
                "#iNext",                      # 下一步
            ]
            for sel in skip_selectors:
                btn = self.page.ele(sel, timeout=1)
                if btn:
                    btn.click()
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击 {sel}")
                    time.sleep(2)
                    return
        except:
            pass

    def _handle_stay_signed_in(self):
        """处理"保持登录状态"弹窗"""
        time.sleep(2)
        try:
            page_text = self.page.html or ""
            # 判断是否在"保持登录"弹窗
            if "保持" in page_text or "Stay signed in" in page_text or "stay" in page_text.lower() or "KMSI" in page_text:
                # 新版 Fluent UI
                btn = self.page.ele('css:button[data-testid="primaryButton"]', timeout=3)
                if btn:
                    btn.click()
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已确认「保持登录」(Fluent UI)")
                    time.sleep(2)
                    return
                # 旧版
                btn = self.page.ele("#idSIButton9", timeout=3)
                if btn:
                    btn.click()
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已确认「保持登录」(Classic)")
                    time.sleep(2)
                    return
                # 文本查找
                for text in ["是", "Yes"]:
                    btn = self.page.ele(f'tag:button@@text()={text}', timeout=1)
                    if btn:
                        btn.click()
                        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已确认「保持登录」")
                        time.sleep(2)
                        return
        except:
            pass

    # ===========================
    # Cookie 登录
    # ===========================
    def login_with_cookie(self, cookie_str, account_index=1):
        """使用已保存的 Cookie 尝试登录"""
        logger.info(f"{LogIcon.COOKIE} {LogTag.LOGIN} 账号{account_index} 尝试 Cookie 登录...")
        try:
            cookies = json.loads(cookie_str)
            if not cookies:
                logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} Cookie 为空")
                return False

            # 先访问 rewards.bing.com 以设置域
            self.page.get(BING_URL)
            time.sleep(10)

            # 注入 Cookie
            injected = 0
            for c in cookies:
                try:
                    self.page.set.cookies(c)
                    injected += 1
                except:
                    pass
            logger.info(f"{LogIndent.L2}{LogTag.COOKIE} 已注入 {injected}/{len(cookies)} 个 Cookie")

            # 刷新页面验证
            self.page.refresh()
            time.sleep(random.uniform(2, 4))

            login_btn = None
            try:
                # 检查页面右上角是否显示登录按钮（id="id_l" 等待时间从2适当调整，增加兼容性）
                login_btn = self.page.ele('#id_l', timeout=2)
                if login_btn:
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 尝试点击右上角登录按钮...")
                    login_btn.click()
                    # 按照用户提供的代码增加随机等待
                    time.sleep(random.uniform(8, 10))
            except:
                pass

            # 验证是否登录成功
            return self._verify_login(account_index)

        except json.JSONDecodeError:
            logger.error(f"{LogIcon.FAIL} {LogTag.COOKIE} 格式无效 (非 JSON)")
            return False
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} Cookie 登录异常: {e}")
            return False

    def _verify_login(self, account_index=1):
        """验证是否已成功登录 Rewards（通过 /dashboard 页面）"""
        try:
            self.page.get(REWARDS_URL)
            time.sleep(10)

            # 如果被重定向到登录页，说明未登录
            current_url = self.page.url or ""
            if "login" in current_url.lower() or "signin" in current_url.lower():
                logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 账号{account_index} 未登录")
                return False

            page_html = self.page.html or ""
            # 检查 /dashboard 页面是否包含积分相关数据
            if '"balance"' in page_html or "availablePoints" in page_html or "仪表板" in page_html or "dashboard" in page_html:
                logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 登录验证通过")
                return True

            return False
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 验证异常: {e}")
            return False

    def get_rewards_points(self, account_index=1, silent=False):
        """从 /earn 页面获取积分和今日详情"""
        try:
            if not silent:
                logger.info(f"{LogIndent.L2}⚙️ [Points] 尝试通过代理访问 Welcome 页面初始化环境...")
            
            # 1. 动态获取品赞代理
            proxy_url = get_pinzan_proxy()
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            
            # 2. 组装请求头（最关键的是把当前浏览器的 Cookie 塞进去）
            headers = {
                "User-Agent": self.page.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cookie": self._get_cookie_header()
            }
            
            if proxy_url and not silent:
                logger.info(f"{LogIndent.L2}   -> 已提取代理，正在使用 {proxy_url} 预热...")
                
            # 3. 发送带有代理的后台请求
            welcome_url = "https://rewards.bing.com/welcome?rh=C21C0DC9&ref=rafsrchae"
            resp = requests.get(welcome_url, headers=headers, proxies=proxies, timeout=15)
            
            if resp.status_code == 200 and not silent:
                logger.info(f"{LogIndent.L2}   -> Welcome 页面代理加载成功！")
            
            # 留出一点时间给微软后台同步状态
            time.sleep(3)
        except Exception as e:
            if not silent:
                logger.warning(f"{LogIcon.WARN} {LogTag.POINTS} 代理访问预热失败: {e}")

        try:
            # === 通过 HTTP (Requests) 提取 /earn 页面的 RSC 数据 ===
            # 直接通过 API 抓取 HTML 避免 DrissionPage UI 渲染导致的 Timeout
            rsc_data = ''
            js_data = {}
            max_reload = 3
            
            for reload_idx in range(max_reload):
                try:
                    headers = {
                        "User-Agent": self.page.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                        "Accept-Encoding": "gzip, deflate, br, zstd",
                        "x-edge-shopping-flag": "1",
                        "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": "https://rewards.bing.com/earn",
                        "upgrade-insecure-requests": "1",
                        "Cookie": self._get_cookie_header()
                    }
                    req_resp = requests.get(REWARDS_EARN_URL, headers=headers, timeout=15)
                    
                    if req_resp.status_code == 200:
                        # 预处理：将已转义的双引号恢复，增强正则匹配成功率
                        rsc_data = req_resp.text.replace('\\"', '"').replace('\\\\', '\\')
                        html_curr = rsc_data

                        if "积分商城错误" in html_curr or "rewards-404-error" in html_curr:
                            
                            # === 新增：第一次报错时尝试自动激活积分商城 ===
                            if reload_idx == 0: 
                                if not silent:
                                    logger.warning(f"{LogIndent.L2}{LogIcon.WARN} {LogTag.POINTS} 检测到未激活商城，尝试自动修复...")
                                try:
                                    # 1. 寻找右上角的登录入口 (根据截图，可能是文本"登录"或头像元素)
                                    top_right_login = self.page.ele('text:登录', timeout=2)
                                    if not top_right_login:
                                        top_right_login = self.page.ele('#meControl', timeout=1)
                                    
                                    if top_right_login:
                                        top_right_login.click()
                                        time.sleep(2) # 等待白色个人信息卡片弹出
                                        
                                        # 2. 判断是否弹出包含“退出”的卡片，确认是登录状态
                                        logout_text = self.page.ele('text:退出', timeout=2)
                                        if logout_text:
                                            if not silent:
                                                logger.info(f"{LogIndent.L2}{LogIcon.INFO} [Points] 确认处于登录态，准备点击加入商城...")
                                            
                                            # 点击页面空白处收起白色卡片，防止遮挡中间的加入按钮
                                            self.page.run_js('document.body.click();')
                                            time.sleep(1)
                                            
                                            # 3. 寻找并点击蓝色的大按钮“加入微软积分商城”
                                            join_btn = self.page.ele('text:加入微软积分商城', timeout=3)
                                            if not join_btn:
                                                # 英文环境兼容
                                                join_btn = self.page.ele('text:Join Microsoft Rewards', timeout=1)
                                                 
                                            if join_btn:
                                                join_btn.click()
                                                if not silent:
                                                    logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} [Points] 成功点击加入积分商城！")
                                                # 给它足够的加载和注册时间
                                                time.sleep(6)
                                                # 刷新一下页面，让浏览器的 Cookie 彻底同步新的激活状态
                                                self.page.refresh()
                                                time.sleep(3)
                                except Exception as e:
                                    pass
                            # === 新增逻辑结束 ===
                            
                            if reload_idx < max_reload - 1:
                                if not silent:
                                    logger.warning(f"{LogIcon.WARN} {LogTag.POINTS} 遇到积分商城错误，等待 5s 后重新加载 ({reload_idx+1}/{max_reload})...")
                                time.sleep(5)
                                continue
                            else:
                                if not silent:
                                    logger.error(f"{LogIcon.FAIL} {LogTag.POINTS} 多次重试依然是积分商城错误")
                        break
                    else:
                        logger.warning(f"{LogIcon.WARN} {LogTag.POINTS} 访问/earn HTTP状态异常: {req_resp.status_code}")
                        time.sleep(5)
                except Exception as e:
                    logger.warning(f"{LogIcon.WARN} {LogTag.POINTS} HTTP获取 RSC 数据报错: {e}")
                    time.sleep(5)

            # if not silent:
            #     logger.info(f"{LogIndent.L2}📦 [Points] RSC 数据长度: {len(rsc_data)}")
            
            # 缓存 RSC 数据，供 quest 解析复用
            self._last_rsc_data = rsc_data
            
            # 如果依然拿不到关键信息，打印少量源文件供分析
            if len(rsc_data) < 60000:
                if not silent:
                    logger.warning(f"{LogIcon.WARN} {LogTag.POINTS} RSC 长度异常 (<60k)，可能发生重定向或未登录。源码前500字符: {rsc_data[:500]}")

            # 从已解码的 RSC 数据中用 Python 正则直接提取关键数值
            # rsc_data 已经是解码后的字符串，"balance":5211 就是标准格式
            if rsc_data:
                # balance
                m = re.search(r'"balance"\s*:\s*(\d+)', rsc_data)
                if m:
                    js_data["balance"] = int(m.group(1))
                # totalPoints
                m = re.search(r'"totalPoints"\s*:\s*(\d+)', rsc_data)
                if m:
                    js_data["totalPoints"] = int(m.group(1))
                # dailyOffer
                m = re.search(r'"dailyOffer"\s*:\s*(\d+)', rsc_data)
                if m:
                    js_data["dailyOffer"] = int(m.group(1))
                # streakCount / streakCounter
                m = re.search(r'"streakCount(?:er)?"\s*:\s*(\d+)', rsc_data)
                if m:
                    js_data["streakCount"] = int(m.group(1))
                # 搜索进度：从 pointsCounters 块中提取 pc.max 和 pc.progress
                m = re.search(r'"pointsCounters"\s*:\s*\{(.*?)\}', rsc_data, re.DOTALL)
                if m:
                    counters_block = m.group(1)
                    # 找 pc 块
                    pc_m = re.search(r'"pc"\s*:\s*\{([^}]+)\}', counters_block)
                    if pc_m:
                        pc_block = pc_m.group(1)
                        max_m = re.search(r'"max"\s*:\s*(\d+)', pc_block)
                        prog_m = re.search(r'"progress"\s*:\s*(\d+)', pc_block)
                        if max_m:
                            js_data["searchMax"] = int(max_m.group(1))
                        if prog_m:
                            js_data["searchProgress"] = int(prog_m.group(1))
                if not silent:
                    logger.info(f"{LogIndent.L2}🧬 [Points] 提取结果: {js_data}")

            # --- 总积分（优先 JS，fallback 正则）---
            points = js_data.get("balance", 0)
            if not points:
                m = re.search(r'"balance"\s*:\s*(\d+)', rsc_data)
                if m:
                    points = int(m.group(1))
                else:
                    m = re.search(r'"availablePoints"\s*:\s*(\d+)', rsc_data)
                    if m:
                        points = int(m.group(1))

            # --- 今日积分 ---
            today_points = js_data.get("totalPoints", 0)
            if not today_points:
                m = re.search(r'"totalPoints"\s*:\s*(\d+)', rsc_data)
                if m:
                    today_points = int(m.group(1))

            # --- 搜索进度（统一搜索）---
            search_progress = js_data.get("searchProgress", 0)
            search_max = js_data.get("searchMax", 0)
            if not search_max:
                m = re.search(r'"pc"\s*:\s*\{[^}]*"max"\s*:\s*(\d+)[^}]*"progress"\s*:\s*(\d+)', rsc_data)
                if not m:
                    m = re.search(r'"pc"\s*:\s*\{[^}]*"progress"\s*:\s*(\d+)[^}]*"max"\s*:\s*(\d+)', rsc_data)
                    if m:
                        search_progress = int(m.group(1))
                        search_max = int(m.group(2))
                else:
                    search_max = int(m.group(1))
                    search_progress = int(m.group(2))

            # --- 每日活动积分 ---
            daily_offer_points = js_data.get("dailyOffer", 0)
            if not daily_offer_points:
                m = re.search(r'"dailyOffer"\s*:\s*(\d+)', rsc_data)
                if m:
                    daily_offer_points = int(m.group(1))

            # --- 连胜信息 ---
            streaks = self._parse_streaks(rsc_data)

            # --- 任务 (Quests) ---
            quests_earned = 0
            quests_total = 0
            quests_progress = 0
            quests_max = 0

            # 定位 Earn_QuestSection 区域
            quest_idx = rsc_data.find('Earn_QuestSection')
            if quest_idx != -1:
                quest_section = rsc_data[quest_idx:min(len(rsc_data), quest_idx + 15000)]
                # 匹配进度，诸如 \"children\":\"0/4 个任务\" 或 "children":"0/4"
                m_prog = re.search(r'(?:\\"|")children(?:\\"|")\s*:\s*(?:\\"|")(\d+)\s*/\s*(\d+).*?(?:\\"|")', quest_section)
                if m_prog:
                    quests_progress = int(m_prog.group(1))
                    quests_max = int(m_prog.group(2))
                    
                # 匹配分数，诸如 [\"+\",\"50\"]
                m_points = re.search(r'\[\s*(?:"|\\")\+(?:"|\\")\s*,\s*(?:"|\\")(\d+)(?:"|\\")\s*\]', quest_section)
                if not m_points:
                    # 备用匹配，寻找带有 +号和数字的结构
                    m_points = re.search(r'(?:"|\\")\+(?:"|\\")[^\d]*?(\d+)', quest_section)
                if m_points:
                    quests_total = int(m_points.group(1))

                if quests_progress > 0 and quests_progress >= quests_max:
                    quests_earned = quests_total

            # --- 活动卡片 (继续赚取 / Keep Earning) ---
            activities = self._parse_activity_cards(rsc_data)
            # 过滤掉 0 分、推广活动（如 RAF、抽奖等）以及未解锁的任务卡片
            scored_activities = [
                a for a in activities
                if a.get("points", 0) > 0
                and a.get("isUnlocked", True)
                and not a.get("isPromotional", False)
            ]
            activity_earned = sum(a.get("points", 0) for a in scored_activities if a.get("isCompleted"))
            activity_total = sum(a.get("points", 0) for a in scored_activities)
            activity_completed_count = sum(1 for a in scored_activities if a.get("isCompleted"))
            activity_all_count = len(scored_activities)

            # --- 等级信息 ---
            level_name = ""
            m = re.search(r'"activeLevelName"\s*:\s*"([^"]+)"', rsc_data)
            if m:
                level_name = m.group(1)
            if not level_name:
                m = re.search(r'"levelName"\s*:\s*"([^"]+)"', rsc_data)
                if m:
                    level_name = m.group(1)

            # --- 计算剩余搜索次数 ---
            search_points_per = 3  # 默认每次搜索3分
            if search_max > 0:
                # 根据总分推算每次搜索积分
                if search_max in [90, 102, 30]:
                    search_points_per = 3
                elif search_max in [55, 150, 170]:
                    search_points_per = 5
                else:
                    search_points_per = 3
            remaining_searches = int((search_max - search_progress) / search_points_per) if search_points_per > 0 and search_max > 0 else 0

            # === 输出日志 ===
            # logger.info(f"{LogIcon.POINTS} {LogTag.POINTS} 账号{account_index} 总积分: {points}" + (f" | {level_name}" if level_name else ""))
            # logger.info(f"{LogIndent.L2}{LogIcon.DATA} 今日积分: {today_points}")
            # if search_max > 0:
            #     logger.info(f"{LogIndent.L2}{LogIcon.SEARCH} 搜索进度: {search_progress}/{search_max} 分 (剩余{remaining_searches}次)")
            # if quests_max > 0 or quests_total > 0:
            #     logger.info(f"{LogIndent.L2}{LogIcon.INFO} 任务: {quests_earned}/{quests_total} 分 ({quests_progress}/{quests_max})")
            # if activity_total > 0:
            #     logger.info(f"{LogIndent.L2}{LogIcon.INFO} 继续赚取: {activity_earned}/{activity_total} ({activity_completed_count}/{activity_all_count})")
            # if streaks:
            #     streak_parts = []
            #     for sk, sv in streaks.items():
            #         streak_parts.append(f"{sk}={sv}")
            #     logger.info(f"{LogIndent.L2_END}{LogIcon.DATA} 连胜: {' | '.join(streak_parts)}")

            return {
                "points": points,
                "level": level_name,
                "today_points": today_points,
                "search": {"progress": search_progress, "max": search_max, "remaining": remaining_searches},
                "daily_offer": daily_offer_points,
                "quests": {"earned": quests_earned, "total": quests_total, "progress": quests_progress, "max": quests_max},
                "activities": {"earned": activity_earned, "total": activity_total, "completed": activity_completed_count, "all": activity_all_count, "details": scored_activities},
                "streaks": streaks,
            }

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.POINTS} 获取积分异常: {e}")
            return None

    def _parse_streaks(self, rsc_data):
        """从 /earn 页面解析连胜信息"""
        streaks = {}
        try:
            # 搜索连胜
            m = re.search(r'"streakCount"\s*:\s*(\d+)', rsc_data)
            if m:
                streaks["连胜天数"] = f"{m.group(1)}天"

            # 从页面可见文本提取更详细的连胜
            page_text = ""
            try:
                page_text = self.page.run_js("return document.body.innerText") or ""
            except:
                pass

            if page_text:
                # 搜索连胜进度（如 3/3）
                m = re.search(r'(?:搜索连胜|Search streak).*?(\d+)/(\d+)', page_text, re.DOTALL)
                if m:
                    streaks["搜索"] = f"{m.group(1)}/{m.group(2)}"
                # 应用连胜进度
                m = re.search(r'(?:应用连胜|App streak).*?(\d+)/(\d+)', page_text, re.DOTALL)
                if m:
                    streaks["应用"] = f"{m.group(1)}/{m.group(2)}"
                # 集章进度
                m = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:stamps|集章)', page_text, re.DOTALL)
                if m:
                    streaks["集章"] = f"{m.group(1)}/{m.group(2)}"
        except:
            pass
        return streaks

    def _parse_activity_cards(self, rsc_data):
        """从 /earn 页面 RSC 数据解析活动卡片 (继续赚取/More Activities)"""
        cards = []

        try:
            # 只在 MoreActivities 作用域内定位 activityCards，避免误命中其它区块
            # 兼容 \"MoreActivities\" 和 "MoreActivities"
            anchor_pattern = re.compile(
                r'(?:"|\\")MoreActivities(?:"|\\").{0,1500}?(?:"|\\")activityCards(?:"|\\")\s*:\s*\[',
                re.DOTALL
            )
            match = anchor_pattern.search(rsc_data)
            if not match:
                logger.warning(f"{LogIcon.WARN} {LogTag.ACTIVITY} 未找到 MoreActivities.activityCards 区块")
                return cards

            start = match.end() - 1

            # 括号匹配提取完整数组
            depth = 0
            end = -1
            for j in range(start, min(len(rsc_data), start + 120000)):
                if rsc_data[j] == '[':
                    depth += 1
                elif rsc_data[j] == ']':
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break

            if end <= 0:
                logger.warning(f"{LogIcon.WARN} {LogTag.ACTIVITY} activityCards 数组括号匹配失败")
                return cards

            arr_str = rsc_data[start:end]

            # 优先走 JSON 解码
            clean_arr = arr_str.replace('\\"', '"')
            try:
                cards_data = json.loads(clean_arr)
            except Exception:
                cards_data = []

            # 辅助转换函数
            def to_bool(v, d=False):
                if isinstance(v, bool): return v
                if isinstance(v, (int, float)): return bool(v)
                s = str(v).strip().lower()
                return True if s in ("true", "1", "yes") else False if s in ("false", "0", "no") else d

            def to_int(v, d=0):
                try: return int(str(v).strip())
                except: return d

            if isinstance(cards_data, list) and len(cards_data) > 0:
                for item in cards_data:
                    if not isinstance(item, dict): continue
                    cards.append({
                        "offerId": str(item.get("offerId", "")),
                        "isCompleted": to_bool(item.get("isCompleted"), False),
                        "points": to_int(item.get("points"), 0),
                        "isUnlocked": to_bool(item.get("isUnlocked"), True),
                        "isPromotional": to_bool(item.get("isPromotional"), False),
                    })
            else:
                # 降级：正则匹配提取，限制在 MoreActivities 内
                for segment in re.split(r'\}\s*,\s*\{', arr_str):
                    o = re.search(r'"offerId"\s*:\s*"([^"]+)"', segment)
                    if not o: continue

                    c = re.search(r'"isCompleted"\s*:\s*(true|false|(?:"|\\")true(?:"|\\")|(?:"|\\")false(?:"|\\"))', segment)
                    p = re.search(r'"points"\s*:\s*(-?\d+)', segment)
                    u = re.search(r'"isUnlocked"\s*:\s*(true|false|(?:"|\\")true(?:"|\\")|(?:"|\\")false(?:"|\\")|(?:"|\\")\$undefined(?:"|\\")|"\$undefined")', segment)
                    promo = re.search(r'"isPromotional"\s*:\s*(true|false|(?:"|\\")true(?:"|\\")|(?:"|\\")false(?:"|\\")|(?:"|\\")\$undefined(?:"|\\")|"\$undefined")', segment)

                    cards.append({
                        "offerId": o.group(1),
                        "isCompleted": to_bool(c.group(1) if c else False, False),
                        "points": to_int(p.group(1) if p else 0, 0),
                        "isUnlocked": to_bool(u.group(1) if u else True, True),
                        "isPromotional": to_bool(promo.group(1) if promo else False, False),
                    })

            # 去重：同一 offerId 保留最后一条（较新状态）
            cards = list({c.get("offerId") or f"__idx_{i}": c for i, c in enumerate(cards)}.values())
        except Exception as e:
            logger.warning(f"{LogIcon.WARN} {LogTag.ACTIVITY} 提取 activityCards 失败: {e}")

        return cards

    # ===========================
    # OAuth 刷新令牌获取
    # ===========================
    def get_refresh_token(self, account_index=1):
        """登录成功后，通过 OAuth 流程获取 refresh_token"""
        logger.info(f"{LogIcon.KEY} {LogTag.LOGIN} 账号{account_index} 开始获取刷新令牌...")

        try:
            from urllib.parse import urlparse, parse_qs

            auth_code = None

            # === 方案1：使用 DrissionPage 的网络监听捕获 code ===
            # 回调 URL ?code=xxx 会瞬间被重定向到 ?removed=true
            # 必须在网络请求层面拦截，而非检查 page.url
            try:
                # 启动网络监听，监听包含 oauth20_desktop.srf 的请求
                self.page.listen.start("oauth20_desktop.srf")

                # 访问 OAuth 授权链接
                self.page.get(OAUTH_AUTHORIZE_URL)

                # 等待捕获包含 code 的请求（最多15秒）
                for packet in self.page.listen.steps(timeout=15):
                    req_url = packet.url if hasattr(packet, 'url') else str(packet)
                    if "code=" in req_url and "oauth20_desktop.srf" in req_url:
                        # 从捕获的 URL 中提取 code
                        parsed = urlparse(req_url)
                        params = parse_qs(parsed.query)
                        if "code" in params:
                            auth_code = params["code"][0]
                            logger.info(f"{LogIndent.L2}📡 [Login] 网络监听捕获授权码: {auth_code[:20]}...")
                            break

                self.page.listen.stop()
            except Exception as e:
                logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 网络监听方式失败: {e}")
                try:
                    self.page.listen.stop()
                except:
                    pass

            # === 方案2：通过 JS 在页面跳转前拦截 URL ===
            if not auth_code:
                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 尝试 JS 拦截方式...")
                try:
                    # 注入 JS 在导航前捕获 URL
                    self.page.get("about:blank")
                    time.sleep(1)
                    self.page.run_js("""
                        window.__oauth_code = null;
                        // 重写 location 的 setter 来拦截跳转中的 code
                        var origAssign = window.location.assign;
                        var origReplace = window.location.replace;

                        // 监听所有导航事件
                        document.addEventListener('beforeunload', function(e) {
                            var url = window.location.href;
                            if (url.includes('code=') && url.includes('oauth20_desktop.srf')) {
                                var params = new URLSearchParams(window.location.search);
                                window.__oauth_code = params.get('code');
                            }
                        });
                    """)

                    # 访问授权链接
                    self.page.run_js(f"window.location.href = '{OAUTH_AUTHORIZE_URL}';")
                    time.sleep(5)

                    # 检查当前 URL（可能已经到了 removed=true）
                    current_url = self.page.url or ""
                    if "code=" in current_url:
                        parsed = urlparse(current_url)
                        params = parse_qs(parsed.query)
                        if "code" in params:
                            auth_code = params["code"][0]
                            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} URL直接捕获授权码: {auth_code[:20]}...")

                    # 检查 JS 变量
                    if not auth_code:
                        try:
                            code_from_js = self.page.run_js("return window.__oauth_code;")
                            if code_from_js:
                                auth_code = code_from_js
                                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} JS拦截捕获授权码: {auth_code[:20]}...")
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} JS 拦截方式失败: {e}")

            # === 方案3：使用 performance API 从浏览器导航记录提取 ===
            if not auth_code:
                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 尝试浏览器历史记录方式...")
                try:
                    # 从 performance entries 中查找包含 code= 的 URL
                    entries = self.page.run_js("""
                        var entries = performance.getEntriesByType('navigation')
                            .concat(performance.getEntriesByType('resource'));
                        var results = [];
                        for (var e of entries) {
                            if (e.name && e.name.includes('code=') && e.name.includes('oauth20_desktop.srf')) {
                                results.push(e.name);
                            }
                        }
                        return results;
                    """)
                    if entries and len(entries) > 0:
                        parsed = urlparse(entries[0])
                        params = parse_qs(parsed.query)
                        if "code" in params:
                            auth_code = params["code"][0]
                            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 历史记录捕获授权码: {auth_code[:20]}...")
                except Exception as e:
                    logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 历史记录方式失败: {e}")

            if not auth_code:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 所有方式均未能获取授权码")
                logger.error(f"{LogIndent.L2}{LogTag.LOGIN} 当前URL: {self.page.url}")
                return None

            # === 第二步：用 authorization code 换取 refresh_token ===
            logger.info(f"{LogIndent.L2}🔄 [Login] 正在换取刷新令牌...")
            import requests as req
            token_data = {
                "client_id": OAUTH_CLIENT_ID,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": OAUTH_REDIRECT_URI,
                "scope": OAUTH_SCOPE,
            }

            resp = req.post(OAUTH_TOKEN_URL, data=token_data, timeout=15)

            if resp.status_code != 200:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 令牌请求失败，状态码: {resp.status_code}")
                logger.error(f"{LogIndent.L2}{LogTag.LOGIN} 响应: {resp.text[:200]}")
                return None

            result = resp.json()
            refresh_token = result.get("refresh_token")
            access_token = result.get("access_token")

            if not refresh_token:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 响应中未找到 refresh_token")
                logger.error(f"{LogIndent.L2}{LogTag.LOGIN} 响应内容: {json.dumps(result, indent=2)[:300]}")
                return None

            logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 刷新令牌获取成功!")
            # logger.info(f"{LogIndent.L2}[Login] refresh_token: {refresh_token[:20]}...({len(refresh_token)}字符)")
            # if access_token:
            #     logger.info(f"{LogIndent.L2}[Login] access_token: {access_token[:20]}...({len(access_token)}字符)")

            return {
                "refresh_token": refresh_token,
                "access_token": access_token,
            }

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 获取刷新令牌异常: {e}")
            return None

    # ===========================
    # 阅读任务相关方法
    # ===========================
    def complete_search_tasks(self, account_index=1):
        """按剩余进度执行搜索任务（使用浏览器模拟真实搜索）"""
        logger.info(f"{LogIcon.SEARCH} {LogTag.SEARCH} 账号{account_index} 准备执行搜索任务")

        points_data = self.get_rewards_points(account_index, silent=True)
        if not points_data:
            logger.warning(f"{LogIcon.WARN} {LogTag.SEARCH} 无法获取搜索进度，跳过搜索任务")
            return 0

        search_info = points_data.get("search", {})
        remaining = int(search_info.get("remaining", 0) or 0)
        progress = int(search_info.get("progress", 0) or 0)
        max_points = int(search_info.get("max", 0) or 0)

        logger.info(f"{LogIndent.L2}📝 当前搜索进度: {progress}/{max_points}，预计剩余 {remaining} 次")
        if remaining <= 0:
            logger.success(f"{LogIndent.L2}✅ 账号{account_index} 搜索任务已完成，无需继续")
            return 0

        logger.info(f"{LogIndent.L2}🌐 开始使用浏览器真实执行模拟搜索...")
        success_count = 0
        from urllib.parse import quote

        # 访问搜索主页
        try:
            self.page.get(SEARCH_HOME_CN_URL)
            time.sleep(random.uniform(2, 4))
            
            # 再刷新一次确保页面完全加载（兼容可能带出的 SSO 重定向状态）
            self.page.refresh()
            time.sleep(random.uniform(2, 4))
            
            # 检查页面右上角是否显示登录按钮（id="id_l" 或 也就是未登录状态的占位符）
            # 只有出现了就点击，因为已经有 live.com 的 token，点击会秒登
            try:
                login_btn = self.page.ele('#id_l', timeout=2)
                if login_btn:
                    logger.info(f"{LogIndent.L2}🔄 尝试点击右上角登录按钮恢复状态...")
                    login_btn.click()
                    time.sleep(random.uniform(8, 10))
            except:
                pass
            
        except Exception as e:
            logger.warning(f"{LogIndent.L2}⚠️ 访问与同步搜索主页状态异常: {e}")

        # 开始循环搜索
        for i in range(remaining):
            logger.info(f"{LogIndent.L2}🔍 正在执行搜索 {i + 1}/{remaining}")
            # 从全局热搜词库取新词
            search_str = hot_words_manager.get_random_word()
            search_url = f"{SEARCH_REQUEST_URL}?q={quote(search_str)}&FORM=ASPN01"
            
            try:
                self.page.get(search_url)
                # 等待加载
                self.page.wait.load_start()
                time.sleep(random.uniform(4, 7))
                success_count += 1
                logger.info(f"{LogIndent.L2}✨ 第 {i + 1}/{remaining} 次搜索完成 ({search_str})")
            except Exception as e:
                logger.warning(f"{LogIndent.L2}❌ 第 {i + 1}/{remaining} 次搜索异常: {e}")
                time.sleep(random.uniform(2, 4))

        logger.success(f"{LogIndent.L2}🎯 账号{account_index} 搜索任务结束，执行 {success_count}/{remaining} 次")
        return success_count

    @retry_decorator(retries=3)
    def get_access_token(self, refresh_token: str) -> dict:
        """使用 refresh_token 获取 access_token 和新的 refresh_token"""
        url = "https://login.live.com/oauth20_token.srf"
        data = {
            'client_id': OAUTH_CLIENT_ID,
            'refresh_token': refresh_token,
            'scope': OAUTH_SCOPE,
            'grant_type': 'refresh_token'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.131",
            'Origin': 'https://login.live.com',
        }
        resp = requests.post(url, data=data, headers=headers, timeout=15)
        if resp.status_code == 200:
            json_data = resp.json()
            return {
                "access_token": json_data.get('access_token'),
                "refresh_token": json_data.get('refresh_token')
            }
        logger.error(f"{LogIcon.FAIL} {LogTag.READ} 刷新访问令牌失败: {resp.status_code}")
        return None

    @retry_decorator(retries=3)
    def get_read_progress(self, access_token: str) -> dict:
        """获取阅读进度"""
        url = "https://prod.rewardsplatform.microsoft.com/dapi/me?channel=SAAndroid&options=613"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': "Mozilla/5.0 (Linux; Android 14; 2210132C Build/UP1A.231005.007) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.52 Mobile Safari/537.36",
            'x-rewards-partnerid': 'startapp',
            'x-rewards-appid': 'SAAndroid/32.2.430730002',
            'x-rewards-country': 'cn',
            'x-rewards-language': 'zh-hans',
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            promotions = data.get('response', {}).get('promotions', [])
            for p in promotions:
                if p.get('attributes', {}).get('offerid') == 'ENUS_readarticle3_30points':
                    return {
                        'max': int(p['attributes'].get('max', 0)),
                        'progress': int(p['attributes'].get('progress', 0))
                    }
            return {'max': 0, 'progress': 0}
        logger.error(f"{LogIcon.FAIL} {LogTag.READ} 获取阅读进度失败: {resp.status_code}")
        return {'max': 0, 'progress': 0}

    @retry_decorator(retries=3)
    def app_sign_in(self, access_token: str, account_index: int = 1) -> int:
        """执行App端每日签到任务"""
        try:
            url = "https://prod.rewardsplatform.microsoft.com/dapi/me/activities"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "channel": "SAAndroid",
                "User-Agent": "okhttp/4.9.1",
                "Authorization": f"Bearer {access_token}"
            }
            
            import time
            current_date = time.localtime()
            date_num = int(f"{current_date.tm_year}{current_date.tm_mon:02d}{current_date.tm_mday:02d}")
            
            payload = {
                "amount": 1,
                "attributes": {
                    "offerid": "Gamification_Sapphire_DailyCheckIn",
                    "date": date_num,
                    "signIn": False,
                    "timezoneOffset": "08:00:00"
                },
                "id": "",
                "type": 101,
                "country": "cn",
                "risk_context": {},
                "channel": "SAAndroid"
            }
            
            time.sleep(random.uniform(2, 4))
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if resp.status_code == 200:
                result = resp.json()
                points_earned = result.get("response", {}).get("activity", {}).get("p", 0)
                time.sleep(random.uniform(2, 4))
                if points_earned > 0:
                    logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} {LogTag.READ} APP签到成功，获得 {points_earned} 积分")
                else:
                    logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} {LogTag.READ} APP今日已签到")
                return points_earned
            else:
                try:
                    error_msg = resp.json().get('error', {}).get('description', '')
                    if 'already' in error_msg.lower() or 'duplicate' in error_msg.lower():
                        logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} {LogTag.READ} APP今日已签到")
                        return 0
                except:
                    pass
                logger.error(f"{LogIndent.L2}{LogIcon.FAIL} {LogTag.READ} APP签到请求失败: {resp.status_code}")
                return -1
                
        except Exception as e:
            error_message = str(e).lower()
            if 'already' in error_message or 'duplicate' in error_message:
                logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} {LogTag.READ} APP今日已签到")
                return 0
            logger.error(f"{LogIndent.L2}{LogIcon.FAIL} {LogTag.READ} APP签到执行异常: {e}")
            return -1

    def complete_app_sign_in_task(self, refresh_token: str, account_index: int = 1) -> int:
        """从主流程独立发起的 APP 每日签到步骤"""
        logger.info(f"{LogIcon.READ} {LogTag.READ} 账号{account_index} 开始执行 APP 签到任务")
        if not refresh_token:
            logger.warning(f"{LogIcon.WARN} {LogTag.READ} 无有效刷新令牌，跳过 APP 签到")
            return 0
        
        token_data = self.get_access_token(refresh_token)
        if not token_data or not token_data.get("access_token"):
            return 0
            
        return self.app_sign_in(token_data["access_token"], account_index)

    @retry_decorator(retries=3)
    def submit_read_activity(self, access_token: str) -> bool:
        """提交一篇新闻的阅读"""
        url = "https://prod.rewardsplatform.microsoft.com/dapi/me/activities"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'User-Agent': "Mozilla/5.0 (Linux; Android 14; 2210132C Build/UP1A.231005.007) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.52 Mobile Safari/537.36",
            'x-rewards-partnerid': 'startapp',
            'x-rewards-appid': 'SAAndroid/32.2.430730002',
            'x-rewards-country': 'cn',
            'x-rewards-language': 'zh-hans',
        }
        payload = {
            'amount': 1,
            'country': 'cn',
            'id': secrets.token_hex(32),
            'type': 101,
            'attributes': {
                'offerid': 'ENUS_readarticle3_30points'
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return True
        elif resp.status_code == 400 and 'already' in resp.text.lower():
            # 已经完成
            return True
        logger.error(f"{LogIcon.FAIL} {LogTag.READ} 阅读活动提交失败: {resp.status_code}")
        return False

    def complete_read_tasks(self, refresh_token: str, account_index: int = 1) -> int:
        """独立执行阅读任务"""
        logger.info(f"{LogIcon.READ} {LogTag.READ} 账号{account_index} 开始执行APP阅读任务")
        if not refresh_token:
            logger.warning(f"{LogIcon.WARN} {LogTag.READ} 无有效刷新令牌，跳过阅读任务")
            return 0
        
        token_data = self.get_access_token(refresh_token)
        if not token_data or not token_data.get("access_token"):
            return 0
            
        access_token = token_data["access_token"]
        progress = self.get_read_progress(access_token)
        # MS 返回的是分数（如进度9分，总分30分），每篇3分
        current = progress.get('progress', 0) // 3
        max_reads = progress.get('max', 0) // 3
        
        if max_reads <= 0:
            logger.info(f"{LogIndent.L2}{LogTag.READ} 未获取到阅读任务 (可能您所在地球区无此任务)")
            return 0
            
        logger.info(f"{LogIndent.L2}{LogTag.READ} 当前阅读进度: {current}/{max_reads} 篇")
        if current >= max_reads:
            logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} {LogTag.READ} 账号{account_index} 阅读任务已完成")
            return current * 3
            
        loop_max = max_reads - current
        for i in range(loop_max):
            logger.info(f"{LogIndent.L2}{LogTag.READ} 正在完成第 {i + 1}/{loop_max} 篇阅读...")
            if self.submit_read_activity(access_token):
                logger.info(f"{LogIndent.L2}{LogTag.READ} 第 {i + 1}/{loop_max} 篇阅读成功")
            else:
                logger.warning(f"{LogIcon.WARN} {LogTag.READ} 第 {i + 1}/{loop_max} 篇阅读失败")
            time.sleep(random.uniform(5, 10))
            
        final_progress = self.get_read_progress(access_token)
        new_current = final_progress.get('progress', 0) // 3
        if new_current >= max_reads:
            logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} {LogTag.READ} 账号{account_index} 阅读任务全部完成")
        else:
            logger.info(f"{LogIndent.L2}{LogIcon.INFO} {LogTag.READ} 账号{account_index} 最终阅读进度: {new_current}/{max_reads} 篇")
            
        return new_current * 3

    def complete_dashboard_tasks(self, account_index: int = 1):
        """完成 Dashboard 页面上的每日任务卡片（点击卡片进去浏览一段时间，+10 变绿即完成）"""
        logger.info(f"{LogIcon.INFO} [Dashboard] 账号{account_index} 开始扫描 Dashboard 每日任务卡片...")
        completed_count = 0
        try:
            self.page.get(REWARDS_URL)
            self.page.wait.load_start()
            time.sleep(random.uniform(4, 7))

            # 使用 JS 提取 Dashboard 页面上的任务卡片
            # Dashboard 的卡片通常在 "每日活动"/"Daily Set" 区域，
            # 每个卡片是一个带有 href 的 <a> 标签，内部包含 +10/+20/+30 等积分标识
            js_extract_cards = """
            const cards = [];
            // 在整个 main 区域查找所有带积分标识的链接卡片
            const main = document.querySelector('main, [role="main"]') || document.body;
            const allLinks = main.querySelectorAll('a[href]');

            allLinks.forEach((link, idx) => {
                const href = link.getAttribute('href') || '';
                if (!href || href === '#' || href === '/dashboard') return;

                const fullText = (link.innerText || '').replace(/\\n/g, ' ').trim();
                const innerHTML = link.innerHTML || '';

                // 查找卡片中的积分标识 (+10, +20, +30 等)
                const pointsMatch = fullText.match(/\\+\\s*(\\d+)/);
                if (!pointsMatch) return;
                const points = parseInt(pointsMatch[1], 10);
                if (points <= 0) return;

                // 判断是否已完成：
                // 1. 寻找绿色对勾/checkmark 图标
                // 2. 寻找 aria-label 包含"已完成"/"Completed"
                // 3. 检查卡片内的状态色/circle 是否为已完成态
                let isCompleted = false;

                // 方式1：aria-label
                const ariaComplete = link.querySelectorAll(
                    '[aria-label="已完成"], [aria-label="Completed"], [aria-label="Complete"]'
                );
                if (ariaComplete.length > 0) isCompleted = true;

                // 方式2：checkmark 相关 class
                const checkmark = link.querySelector(
                    '[class*="checkmark"], [class*="Checkmark"], span.mee-icon-SkypeCircleCheck, [class*="completedIcon"]'
                );
                if (checkmark) isCompleted = true;

                // 方式3：检查 SVG 或 icon 内是否包含对勾符号（微软常用 Fluent UI 对勾）
                if (innerHTML.includes('SkypeCircleCheck') || innerHTML.includes('CheckMark')) {
                    isCompleted = true;
                }

                // 方式4：检查 +N 文字的颜色是否为绿色（完成态 color 通常为绿色系）
                const pointsEls = link.querySelectorAll('span, p, div');
                for (const el of pointsEls) {
                    const elText = (el.innerText || '').trim();
                    if (elText.match(/^\\+\\s*\\d+$/)) {
                        const style = window.getComputedStyle(el);
                        const color = style.color;
                        // 绿色系 RGB：r < 100, g > 140, b < 100
                        const rgbMatch = color.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
                        if (rgbMatch) {
                            const r = parseInt(rgbMatch[1]);
                            const g = parseInt(rgbMatch[2]);
                            const b = parseInt(rgbMatch[3]);
                            if (g > 140 && r < 120 && b < 120) {
                                isCompleted = true;
                            }
                        }
                        break;
                    }
                }

                // 方式5：检查 data-complete 等自定义属性
                if (link.getAttribute('data-complete') === 'true' ||
                    link.getAttribute('data-completed') === 'true') {
                    isCompleted = true;
                }

                cards.push({
                    href: href,
                    text: fullText.substring(0, 60),
                    points: points,
                    isCompleted: isCompleted,
                    index: idx
                });
            });
            return cards;
            """

            cards = self.page.run_js(js_extract_cards)
            if not cards:
                logger.info(f"{LogIndent.L2}[Dashboard] 未在 Dashboard 上发现任务卡片")
                return 0

            # 去重
            seen_hrefs = set()
            unique_cards = []
            for c in cards:
                if c['href'] not in seen_hrefs:
                    seen_hrefs.add(c['href'])
                    unique_cards.append(c)

            completed_cards = [c for c in unique_cards if c['isCompleted']]
            pending_cards = [c for c in unique_cards if not c['isCompleted']]

            logger.info(f"{LogIndent.L2}[Dashboard] 发现 {len(unique_cards)} 个任务卡片 "
                        f"(已完成 {len(completed_cards)}, 待处理 {len(pending_cards)})")

            if not pending_cards:
                logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} [Dashboard] 所有 Dashboard 任务卡片已完成")
                return 0

            # 逐一点击待完成的卡片
            for i, card in enumerate(pending_cards, 1):
                href = card['href']
                text = card['text'] or '未知任务'
                pts = card['points']
                logger.info(f"{LogIndent.L2}[Dashboard] ({i}/{len(pending_cards)}) 开始执行: {text} (+{pts})")

                try:
                    full_url = href
                    if full_url.startswith('/'):
                        full_url = f"https://rewards.bing.com{full_url}"

                    # 通过真实 DOM 点击操作（_safe_find_link 兼容 href 含引号的情况）
                    link_ele = self._safe_find_link(href)

                    if link_ele:
                        self.page.scroll.to_see(link_ele)
                        time.sleep(0.5)
                        # 强制在新标签页打开
                        link_ele.run_js('this.target="_blank";')
                        link_ele.click()
                        time.sleep(2)
                        new_tab = self.browser.latest_tab
                        if new_tab == self.page:
                            new_tab = self.browser.new_tab(full_url)
                    else:
                        new_tab = self.browser.new_tab(full_url)

                    new_tab.wait.load_start()

                    # 浏览一段时间（模拟真实用户阅读行为）
                    stay_time = random.uniform(8, 15)
                    logger.info(f"{LogIndent.L2}   -> 新标签页已打开，浏览等待 {stay_time:.1f} 秒...")
                    time.sleep(stay_time / 3)

                    # 模拟滚动页面
                    try:
                        new_tab.scroll.down(300)
                        time.sleep(stay_time / 3)
                        new_tab.scroll.down(300)
                    except:
                        pass

                    time.sleep(stay_time / 3)

                    # 关闭新标签页
                    new_tab.close()
                    time.sleep(random.uniform(1, 3))
                    completed_count += 1

                    logger.info(f"{LogIndent.L2}   -> ✅ 卡片浏览完毕并已关闭")

                except Exception as e:
                    logger.error(f"{LogIcon.FAIL} [Dashboard] 任务卡片执行失败: {e}")
                    # 尝试关闭可能残留的标签页
                    try:
                        tabs = self.browser.tab_ids
                        while len(tabs) > 1:
                            latest = self.browser.latest_tab
                            if latest != self.page:
                                latest.close()
                            tabs = self.browser.tab_ids
                    except:
                        pass

            # 回到 Dashboard 检查完成状态
            logger.info(f"{LogIndent.L2}[Dashboard] 所有卡片处理完毕，回到 Dashboard 验证状态...")
            self.page.get(REWARDS_URL)
            self.page.wait.load_start()
            time.sleep(random.uniform(3, 5))

            # 重新检查完成状态
            verify_cards = self.page.run_js(js_extract_cards)
            if verify_cards:
                now_completed = sum(1 for c in verify_cards if c.get('isCompleted'))
                now_total = len(verify_cards)
                logger.info(f"{LogIndent.L2}[Dashboard] 验证结果: {now_completed}/{now_total} 个卡片已完成")
            
            logger.success(f"{LogIcon.SUCCESS} [Dashboard] Dashboard 任务卡片处理完毕，本次处理 {completed_count} 个")

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} [Dashboard] Dashboard 任务执行异常: {e}")

        return completed_count

    def claim_dashboard_rewards(self, account_index: int = 1):
        '''尝试在仪表板领取可提取的积分'''
        claim_points = 0
        try:
            logger.info(f"{LogIcon.INFO} [Dashboard] 账号{account_index} 检查待领取积分...")
            self.page.get("https://rewards.bing.com/dashboard")
            self.page.wait.load_start()
            import time
            import random
            time.sleep(random.uniform(3, 5))
            
            # 第一步：寻找包含“可领取”和金额的区域
            claim_card = self.page.ele('xpath://div[contains(@class,"rewardsBgAlpha1")]/ancestor::button', timeout=2)
            if not claim_card:
                # 兼容查找
                text_ele = self.page.ele('text:可领取', timeout=1)
                if text_ele:
                    claim_card = text_ele.parent(2)
            
            if claim_card:
                text = claim_card.text.replace(',', '')
                import re
                nums = re.findall(r'\d+', text)
                claim_points = 0
                if nums:
                    claim_points = int(nums[0])
                    
                if claim_points > 0:
                    logger.info(f"{LogIndent.L2}[Dashboard] 发现待领取积分: {claim_points} 分，开始领取...")
                    claim_card.click()
                    time.sleep(random.uniform(2, 4))
                    
                    # 第二步：在弹出的侧边栏点击底部“领取积分”按钮
                    # 用更严格的按钮定位，防止找到 script 内的脏文本
                    btn = self.page.ele('xpath://button[span[contains(text(),"领取积分")]]', timeout=3)
                    if not btn:
                         btn = self.page.ele('xpath://button[contains(text(),"Claim points")]', timeout=1)
                    if not btn:
                         btn = self.page.ele('xpath://button[.//text()[contains(., "领取积分")]]', timeout=1)
                         
                    if btn:
                        # 兼容处理在侧边栏元素点击不可见可能失败的情况
                        try:
                            self.page.scroll.to_see(btn)
                        except:
                            pass
                        time.sleep(0.5)
                        btn.click()
                        logger.success(f"{LogIcon.SUCCESS} [Dashboard] 已成功点击领取按钮！")
                        time.sleep(random.uniform(3, 5))
                    else:
                        logger.warning(f"{LogIcon.WARN} [Dashboard] 侧边栏弹出，但未找到领取确认按钮")
                else:
                    logger.info(f"{LogIndent.L2}[Dashboard] 当前无待领取积分 (0)")
            else:
                logger.info(f"{LogIndent.L2}[Dashboard] 当前未发现可领取的积分模块")
            return claim_points
                
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} [Dashboard] 领取积分时发生异常: {e}")
            return claim_points

    def complete_earn_page_tasks(self, account_index: int = 1):
        """完成 Earn 页面上的所有点击任务。
        对英文和中文两套任务系统各执行一次，确保两边积分都能完整获取。"""
        logger.info(f"{LogIcon.INFO} [Earn] 账号{account_index} 开始扫描 Earn 页面任务（英文+中文两套）...")

        for lang, lang_name in [("en", "英文"), ("zh", "中文")]:
            logger.info(f"{'─' * 40}")
            logger.info(f"{LogIcon.INFO} [Earn] === 处理 {lang_name} 版本的 Earn 任务 ===")
            switched = self.switch_display_language(lang, account_index)
            if not switched:
                logger.warning(f"{LogIcon.WARN} [Earn] 切换到{lang_name}失败，跳过{lang_name}版任务")
                continue
            self._execute_earn_tasks_on_current_language(account_index)

        logger.success(f"{LogIcon.SUCCESS} [Earn] 英文+中文两套 Earn 任务均已处理完毕")

    def _execute_earn_tasks_on_current_language(self, account_index: int = 1):
        """在当前显示语言下，扫描并执行 Earn 页面的所有点击任务（内部实现）。"""
        try:
            self.page.get("https://rewards.bing.com/earn")
            self.page.wait.load_start()
            time.sleep(random.uniform(5, 8))

            # 先滚动到底部再回顶，确保懒加载的日常任务卡片全部渲染
            try:
                self.page.scroll.to_bottom()
                time.sleep(2)
                self.page.scroll.to_top()
                time.sleep(1)
            except:
                pass
            
            # 使用 JS 提取页面上的所有任务链接（含日常任务）
            js_code = """
            const tasks = [];
            const main = document.querySelector('main, [role="main"]') || document.body;
            const links = main.querySelectorAll('a[href]');

            links.forEach((link, idx) => {
                const href = link.getAttribute('href') || '';
                if (!href || href === '#' || href === '/earn' || href === '/dashboard') return;

                const text = (link.innerText || '').replace(/\\n/g, ' ').trim();
                const innerHTML = link.innerHTML || '';

                // === 积分检测（多策略） ===
                let points = null;

                // 策略1：精确 class 查找（原有逻辑）
                const pointsEl = link.querySelector('.text-caption1Stronger');
                if (pointsEl) {
                    points = pointsEl.innerText.trim();
                }

                // 策略2：在卡片文本里匹配 +N 模式（覆盖日常任务）
                if (!points) {
                    const plusMatch = text.match(/\\+\\s*(\\d+)/);
                    if (plusMatch) {
                        points = '+' + plusMatch[1];
                    }
                }

                // 策略3：在子元素中搜索包含 +数字 的 span/p/div
                if (!points) {
                    const inlineEls = link.querySelectorAll('span, p, div, strong');
                    for (const el of inlineEls) {
                        const elText = (el.innerText || '').trim();
                        if (/^\\+\\s*\\d+$/.test(elText)) {
                            points = elText;
                            break;
                        }
                    }
                }

                // 没有找到积分标识的链接，跳过
                if (!points) return;

                // 提取纯数字用于后续记录
                const numMatch = points.match(/(\\d+)/);
                const pointsNum = numMatch ? parseInt(numMatch[1], 10) : 0;

                // === 完成状态检测（多策略） ===
                const circleEl = link.querySelector('[class*="rounded-full"], [class*="circle"]');
                const circleClass = circleEl ? Array.from(circleEl.classList || []).join(' ') : '';
                
                let isCompleted = false;
                
                // 方式1：checkmark 图标
                const checkmark = link.querySelector('[class*="checkmark"], [class*="Checkmark"], span.mee-icon-SkypeCircleCheck, [class*="completedIcon"]');
                if (checkmark || circleClass.includes('f2f2f2') || innerHTML.includes('SkypeCircleCheck') || innerHTML.includes('CheckMark')) {
                    isCompleted = true;
                }
                
                // 方式2：aria-label 完成标记
                const ariaCompleteList = link.querySelectorAll('[aria-label="已完成"], [aria-label="Completed"], [aria-label="Complete"]');
                if (ariaCompleteList.length > 0) {
                    isCompleted = true;
                }

                // 方式3：进度文本 N/N 判断
                const textContent = text.replace(/\\s+/g, '');
                const progressMatch = textContent.match(/(\\d+)\\/((\\d+)(?:[a-zA-Z\\u4e00-\\u9fa5]+)?)/);
                if (progressMatch) {
                    if (progressMatch[1] === progressMatch[3]) {
                        isCompleted = true; 
                    } else {
                        isCompleted = false;
                    }
                }

                // 方式4：+N 文字颜色为绿色（日常任务完成后文字变绿）
                const allSpans = link.querySelectorAll('span, p, div, strong');
                for (const el of allSpans) {
                    const elText = (el.innerText || '').trim();
                    if (/^\\+\\s*\\d+$/.test(elText)) {
                        const style = window.getComputedStyle(el);
                        const color = style.color;
                        const rgbMatch = color.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
                        if (rgbMatch) {
                            const r = parseInt(rgbMatch[1]);
                            const g = parseInt(rgbMatch[2]);
                            const b = parseInt(rgbMatch[3]);
                            // 绿色系判定
                            if (g > 140 && r < 120 && b < 120) {
                                isCompleted = true;
                            }
                        }
                        break;
                    }
                }

                // 方式5：data 属性
                if (link.getAttribute('data-complete') === 'true' ||
                    link.getAttribute('data-completed') === 'true') {
                    isCompleted = true;
                }

                tasks.push({
                    href: href,
                    text: text.substring(0, 60),
                    points: points,
                    pointsNum: pointsNum,
                    isCompleted: isCompleted,
                    circleClass: circleClass
                });
            });
            return tasks;
            """
            
            tasks = self.page.run_js(js_code)
            if not tasks:
                logger.warning(f"{LogIcon.WARN} [Earn] 未能在页面上找到有效任务链接")
                return

            seen = set()
            unique_tasks = []
            for t in tasks:
                if t['href'] not in seen:
                    seen.add(t['href'])
                    unique_tasks.append(t)
            
            completed_tasks = [t for t in unique_tasks if t['isCompleted']]
            pending_tasks = [t for t in unique_tasks if not t['isCompleted']]
            
            logger.info(f"{LogIndent.L2}[Earn] 发现 {len(unique_tasks)} 个有效积分任务 (已完成 {len(completed_tasks)}, 待处理 {len(pending_tasks)})")

            # 打印详细列表
            for t in unique_tasks:
                status = "✅" if t['isCompleted'] else "⬜"
                logger.info(f"{LogIndent.L2}   {status} {t['text']} ({t['points']})")
            
            if not pending_tasks:
                logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} [Earn] 所有 Earn 页面任务已完成")
                return
                
            for i, task in enumerate(pending_tasks, 1):
                href = task['href']
                text = task['text'] or '未知任务'
                pts = task['points'] or '?'
                logger.info(f"{LogIndent.L2}[Earn] ({i}/{len(pending_tasks)}) 开始执行: {text} ({pts})")
                
                try:
                    full_url = href
                    if full_url.startswith('/'):
                        full_url = f"https://rewards.bing.com{full_url}"
                        
                    # 通过真实 DOM 点击操作，防止 telemetry click handler 未触发
                    # _safe_find_link 兼容 href 含引号的情况
                    main_link = self._safe_find_link(href)
                        
                    if main_link:
                        # 滚动可视 + 强制新标签页 + 真实点击
                        self.page.scroll.to_see(main_link)
                        time.sleep(0.5)
                        main_link.run_js('this.target="_blank";')
                        main_link.click()
                        time.sleep(2)
                        new_tab = self.browser.latest_tab
                        if new_tab == self.page:
                            new_tab = self.browser.new_tab(full_url)
                    else:
                        new_tab = self.browser.new_tab(full_url)
                        
                    new_tab.wait.load_start()
                    
                    # ─── 检测是否为 Bing Homepage Quiz（ABC 答题任务）───
                    is_quiz = (
                        'quiz' in full_url.lower()
                        or 'trivia' in full_url.lower()
                        or 'ML2BF' in full_url  # Bing Quiz 特有 form 参数
                    )
                    if not is_quiz:
                        # 等页面加载后，再用 DOM 特征二次确认
                        time.sleep(4)
                        try:
                            quiz_check = new_tab.run_js("""
                                // 检查是否存在 A/B/C 答题选项按钮
                                var btns = document.querySelectorAll(
                                    '[class*="quiz"] button, [class*="Quiz"] button, ' +
                                    '[id*="quiz"] button, [id*="Quiz"] button, ' +
                                    '.b_ans button, .qna button'
                                );
                                if (btns.length > 0) return true;
                                // 检查页面文字是否包含 A. B. C. 格式（多语言兼容）
                                var bodyText = document.body.innerText || '';
                                if (/\\bA\\.\\s/.test(bodyText) && /\\bB\\.\\s/.test(bodyText)) return true;
                                // 检查是否含有 1/3, 1/2 进度提示（测验分页特征）
                                if (/[1-9]\\s*\\/\\s*[2-9]/.test(bodyText)) {
                                    // 同时有选项按钮区域
                                    var optionArea = document.querySelectorAll('[class*="option"], [class*="answer"], [class*="choice"]');
                                    if (optionArea.length > 0) return true;
                                }
                                return false;
                            """)
                            if quiz_check:
                                is_quiz = True
                        except:
                            pass

                    if is_quiz:
                        logger.info(f"{LogIndent.L2}   -> [Quiz] 检测到测验答题任务，开始自动答题...")
                        # 最多循环答 10 题（防止死循环）
                        for quiz_round in range(10):
                            try:
                                time.sleep(3)
                                clicked_option = new_tab.run_js("""
                                    // 策略1：寻找包含 "A." / "B." / "C." 文字的按钮或可点击元素
                                    var allEls = document.querySelectorAll(
                                        'button, [role="button"], [role="radio"], [role="option"], ' +
                                        'li[tabindex], div[tabindex][class*="option"], ' +
                                        'div[tabindex][class*="answer"], div[tabindex][class*="choice"]'
                                    );
                                    for (var el of allEls) {
                                        var t = (el.innerText || el.textContent || '').trim();
                                        // 匹配以 A. / B. / C. 开头的选项（中英文均可）
                                        if (/^[ABC]\\.\\s/i.test(t) && t.length < 120) {
                                            el.scrollIntoView({block: 'center'});
                                            el.click();
                                            return 'clicked_option_text: ' + t.substring(0, 50);
                                        }
                                    }

                                    // 策略2：通过 class 关键字定位答题区域，点击第一个可见选项
                                    var optionSelectors = [
                                        '[class*="quiz"][class*="option"]',
                                        '[class*="quiz"][class*="answer"]',
                                        '[class*="quiz"][class*="choice"]',
                                        '[class*="b_focusableElements"]',
                                        '.b_ans .b_focusLink',
                                        '.wpc_btn',
                                        '[class*="qna"] li',
                                        '[id^="ChoiceA"]', '[id^="ChoiceB"]', '[id^="ChoiceC"]',
                                        '[id^="option"]'
                                    ];
                                    for (var sel of optionSelectors) {
                                        var found = document.querySelectorAll(sel);
                                        if (found.length > 0) {
                                            found[0].scrollIntoView({block: 'center'});
                                            found[0].click();
                                            return 'clicked_by_selector: ' + sel;
                                        }
                                    }

                                    // 策略3：查找 Bing Quiz 常用的 id 或 data 属性
                                    var quizInputs = document.querySelectorAll(
                                        'input[type="radio"], input[type="button"][class*="quiz"]'
                                    );
                                    if (quizInputs.length > 0) {
                                        quizInputs[0].click();
                                        return 'clicked_radio_input';
                                    }

                                    return null;
                                """)

                                if clicked_option:
                                    logger.info(f"{LogIndent.L2}      [Quiz] 第{quiz_round+1}题已选择: {str(clicked_option)[:80]}")
                                    time.sleep(2)

                                    # 检查是否有"下一题"/"Next"/"提交"等按钮
                                    next_clicked = new_tab.run_js("""
                                        var nextTexts = ['下一题', 'Next', 'Submit', '提交', '确认', 'Confirm', '继续', 'Continue'];
                                        var btns = document.querySelectorAll('button, [role="button"], a[class*="next"], a[class*="Next"]');
                                        for (var btn of btns) {
                                            var t = (btn.innerText || btn.textContent || '').trim();
                                            for (var nx of nextTexts) {
                                                if (t.includes(nx) && t.length < 30) {
                                                    btn.scrollIntoView({block: 'center'});
                                                    btn.click();
                                                    return 'clicked_next: ' + t;
                                                }
                                            }
                                        }
                                        return null;
                                    """)
                                    if next_clicked:
                                        logger.info(f"{LogIndent.L2}      [Quiz] 已点击下一步: {str(next_clicked)[:50]}")
                                    time.sleep(2)

                                    # 检查是否已经全部完成（无更多选项可点）
                                    has_more = new_tab.run_js("""
                                        var allEls = document.querySelectorAll(
                                            'button, [role="button"], [role="radio"], [role="option"], ' +
                                            'li[tabindex], div[tabindex][class*="option"], ' +
                                            'div[tabindex][class*="answer"], div[tabindex][class*="choice"]'
                                        );
                                        for (var el of allEls) {
                                            var t = (el.innerText || el.textContent || '').trim();
                                            if (/^[ABC]\\.\\s/i.test(t) && t.length < 120) return true;
                                        }
                                        var optionSelectors = [
                                            '[class*="quiz"][class*="option"]',
                                            '[class*="quiz"][class*="answer"]',
                                            '[id^="ChoiceA"]', '[id^="ChoiceB"]', '[id^="ChoiceC"]',
                                            '[id^="option"]'
                                        ];
                                        for (var sel of optionSelectors) {
                                            if (document.querySelectorAll(sel).length > 0) return true;
                                        }
                                        return false;
                                    """)
                                    if not has_more:
                                        logger.info(f"{LogIndent.L2}   -> [Quiz] 答题任务已全部完成（共 {quiz_round+1} 题）")
                                        break
                                else:
                                    logger.info(f"{LogIndent.L2}   -> [Quiz] 未检测到更多选项，答题结束（共 {quiz_round} 题）")
                                    break
                            except Exception as qe:
                                logger.warning(f"{LogIcon.WARN} [Quiz] 第{quiz_round+1}题执行异常: {qe}")
                                break

                        time.sleep(random.uniform(3, 5))

                    elif '/earn/quest/' in full_url:
                        logger.info(f"{LogIndent.L2}   -> [Quest] 此为打卡任务集，开始扫描子任务...")
                        time.sleep(4)
                        new_tab.scroll.to_bottom()
                        time.sleep(4)
                        
                        subtask_js = """
                        const subtasks = [];
                        const links = document.querySelectorAll('main a[href]');
                        links.forEach((link) => {
                            const href = link.getAttribute('href') || '';
                            if (!href || href === '#' || href.includes('/earn/quest/')) return;
                            
                            const text = (link.innerText || '').replace(/\\n/g, ' ').trim();
                            let isCompleted = false;
                            
                            const checkmark = link.querySelector('[class*="checkmark"], [class*="Checkmark"], span.mee-icon-SkypeCircleCheck, [class*="completedIcon"]');
                            const htmlContent = link.innerHTML || "";
                            if (checkmark || htmlContent.includes('SkypeCircleCheck') || htmlContent.includes('CheckMark')) {
                                isCompleted = true;
                            }
                            
                            const ariaCompleteList = link.querySelectorAll('[aria-label="已完成"], [aria-label="Completed"], [aria-label="Complete"]');
                            if (ariaCompleteList.length > 0) {
                                isCompleted = true;
                            }

                            // 颜色检测
                            const spans = link.querySelectorAll('span, p, div');
                            for (const el of spans) {
                                const elText = (el.innerText || '').trim();
                                if (/^\\+\\s*\\d+$/.test(elText)) {
                                    const style = window.getComputedStyle(el);
                                    const color = style.color;
                                    const rgbMatch = color.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
                                    if (rgbMatch) {
                                        const g = parseInt(rgbMatch[2]);
                                        const r = parseInt(rgbMatch[1]);
                                        const b = parseInt(rgbMatch[3]);
                                        if (g > 140 && r < 120 && b < 120) isCompleted = true;
                                    }
                                    break;
                                }
                            }
                            
                            subtasks.push({href: href, text: text.substring(0, 30), isCompleted: isCompleted});
                        });
                        return subtasks;
                        """
                        
                        subtasks = new_tab.run_js(subtask_js)
                        if subtasks:
                            pending_subtasks = [sub for sub in subtasks if not sub['isCompleted']]
                            logger.info(f"{LogIndent.L2}   -> 发现 {len(subtasks)} 个内部子链接 ({len(pending_subtasks)} 个待点击)")
                            
                            for j, sub in enumerate(pending_subtasks, 1):
                                sub_href = sub['href']
                                logger.info(f"{LogIndent.L2}      - 点击 ({j}): {sub['text']}...")
                                try:
                                    # _safe_find_link 兼容 sub_href 含引号的情况
                                    sub_ele = self._safe_find_link(sub_href, tab=new_tab)
                                        
                                    if sub_ele:
                                        # 点击真子元素触发遥测风控
                                        new_tab.scroll.to_see(sub_ele)
                                        time.sleep(0.5)
                                        sub_ele.run_js('this.target="_blank";')
                                        sub_ele.click()
                                        time.sleep(2)
                                        
                                        sub_tab = self.browser.latest_tab
                                        if sub_tab in (new_tab, self.page):
                                            # 未弹出时回退到 URL 形式的直接访问
                                            abs_sub = sub_href if sub_href.startswith('http') else (f"https://www.bing.com{sub_href}" if sub_href.startswith('/') else sub_href)
                                            sub_tab = self.browser.new_tab(abs_sub)
                                    else:
                                        abs_sub = sub_href if sub_href.startswith('http') else (f"https://www.bing.com{sub_href}" if sub_href.startswith('/') else sub_href)
                                        sub_tab = self.browser.new_tab(abs_sub)
                                        
                                    sub_tab.wait.load_start()
                                    sub_stay_time = random.uniform(8, 15)
                                    logger.info(f"{LogIndent.L2}      - 浏览等待 {sub_stay_time:.1f} 秒...")
                                    time.sleep(sub_stay_time / 3)
                                    try:
                                        sub_tab.scroll.down(300)
                                        time.sleep(sub_stay_time / 3)
                                        sub_tab.scroll.down(300)
                                    except:
                                        pass
                                    time.sleep(sub_stay_time / 3)
                                    sub_tab.close()
                                    time.sleep(2)
                                except Exception as e:
                                    logger.error(f"{LogIcon.FAIL} [Earn] SubTask Error: {e}")
                                    try:
                                        tabs = self.browser.tab_ids
                                        while len(tabs) > 2:
                                            latest = self.browser.latest_tab
                                            if latest not in (self.page, new_tab):
                                                latest.close()
                                            tabs = self.browser.tab_ids
                                    except:
                                        pass
                        else:
                            logger.warning(f"{LogIcon.WARN} [Earn] 未在该 Quest 页面发现子链接节点")
                    else:
                        # 普通日常浏览任务：打开页面，等待浏览一段时间，模拟滚动
                        stay_time = random.uniform(8, 15)
                        logger.info(f"{LogIndent.L2}   -> [Activity] 位于新标签页，浏览等待 {stay_time:.1f} 秒...")
                        time.sleep(stay_time / 3)

                        # 模拟滚动页面（部分任务需要有滚动行为才算有效浏览）
                        try:
                            new_tab.scroll.down(300)
                            time.sleep(stay_time / 3)
                            new_tab.scroll.down(300)
                        except:
                            pass

                        time.sleep(stay_time / 3)
                        
                    new_tab.close()
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.error(f"{LogIcon.FAIL} [Earn] 任务执行失败: {e}")
                    # 清理可能残留的标签页
                    try:
                        tabs = self.browser.tab_ids
                        while len(tabs) > 1:
                            latest = self.browser.latest_tab
                            if latest != self.page:
                                latest.close()
                            tabs = self.browser.tab_ids
                    except:
                        pass
                    
            logger.success(f"{LogIcon.SUCCESS} [Earn] 页面点击任务处理完毕")
            
            # 返回并刷新 earn 页面以同步状态
            self.page.get("https://rewards.bing.com/earn")
            self.page.wait.load_start()
            time.sleep(random.uniform(3, 5))

            # 验证完成情况
            verify_tasks = self.page.run_js(js_code)
            if verify_tasks:
                now_completed = sum(1 for t in verify_tasks if t.get('isCompleted'))
                now_total = len(verify_tasks)
                logger.info(f"{LogIndent.L2}[Earn] 验证结果: {now_completed}/{now_total} 个任务已完成")
            
        except Exception as e:
            logger.error(f"{LogIcon.FAIL} [Earn] 任务流程异常: {e}")




    # ===========================
    # 辅助：切换 Bing 显示语言
    # ===========================
    def switch_display_language(self, lang: str = "en", account_index: int = 1) -> bool:
        """切换 Bing 账号的显示语言。
        lang: 'en' => 英语, 'zh' => 中文(简体)

        Bug 修复历史：
          - href 严格边界匹配，避免 setlang=ar 被 setlang=ar... 误匹配
          - 删除宽泛兜底 || href.includes('setlang')，避免误击第一个语言链接
          - TreeWalker 同时搜索中文名（英语）和英文名（English），覆盖页面当前语言
        """
        import json as _json

        # 实际 URL 中 setlang 参数的候选值（从低到高特异性排列，先试精确值）
        setlang_variants_map = {
            "en":  ["en-us", "en-US", "en"],          # 英文
            "zh":  ["zh-hans", "zh-CN", "zh-cn", "zh"],  # 中文简体
        }
        # 页面上显示的语言名称（可能是中文名或英文名，取决于当前界面语言）
        text_names_map = {
            "en": ["英语", "English"],
            "zh": ["中文(简体)", "中文（简体）", "Chinese (Simplified)"],
        }

        variants  = setlang_variants_map.get(lang)
        textNames = text_names_map.get(lang)
        lang_name = "English" if lang == "en" else "中文(简体)"

        if not variants:
            logger.warning(f"{LogIcon.WARN} [System] 不支持的语言标识: {lang}")
            return False

        lang_url = (
            "https://www.bing.com/account/general"
            "?ru=https%3A%2F%2Fwww.bing.com%2Frewards"
            "&id=language_section#language-section"
        )
        try:
            logger.info(f"{LogIndent.L2}[System] 账号{account_index} 切换显示语言为: {lang_name}")
            self.page.get(lang_url)
            time.sleep(random.uniform(4, 6))

            # 滚动到底部再回顶，触发懒加载渲染
            try:
                self.page.scroll.to_bottom()
                time.sleep(1.5)
                self.page.scroll.to_top()
                time.sleep(1)
                sec = self.page.ele('#language-section', timeout=3)
                if sec:
                    self.page.scroll.to_see(sec)
                    time.sleep(1.5)
            except Exception:
                pass

            # 将 Python 列表序列化为 JS 数组字面量
            variants_js   = _json.dumps([v.lower() for v in variants])
            text_names_js = _json.dumps(textNames)

            clicked = self.page.run_js(f"""
                var variants   = {variants_js};
                var textNames  = {text_names_js};

                // ── 辅助：判断元素是否可点击 ──
                function isClickable(el) {{
                    if (!el || !el.tagName) return false;
                    var tag = el.tagName.toUpperCase();
                    return tag === 'A' || tag === 'BUTTON' ||
                           el.getAttribute('role') === 'button' ||
                           typeof el.onclick === 'function' ||
                           el.getAttribute('onclick');
                }}
                function findClickableAncestor(el) {{
                    for (var i = 0; i < 6; i++) {{
                        if (!el) break;
                        if (isClickable(el)) return el;
                        el = el.parentElement;
                    }}
                    return null;
                }}

                // ── 方法1：TreeWalker 遍历文本节点，匹配语言名称（支持中英文名） ──
                var walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null, false
                );
                var node;
                while (node = walker.nextNode()) {{
                    var t = (node.textContent || '').trim();
                    for (var name of textNames) {{
                        if (t === name || (t.includes(name) && t.length < 40)) {{
                            var clickable = findClickableAncestor(node.parentElement);
                            if (clickable) {{
                                clickable.scrollIntoView({{block: 'center'}});
                                clickable.click();
                                return 'treewalker_click:' + name
                                     + '|tag=' + clickable.tagName
                                     + '|href=' + (clickable.href || clickable.getAttribute('href') || '');
                            }}
                        }}
                    }}
                }}

                // ── 方法2：精确匹配 href 中的 setlang 值（严格边界，不误击其他语言） ──
                // 匹配规则：setlang=<code> 后必须紧跟 & 或 # 或字符串结束
                function hrefMatchesSetlang(href, variant) {{
                    var lh = href.toLowerCase();
                    var pattern = 'setlang=' + variant.toLowerCase();
                    var idx = lh.indexOf(pattern);
                    if (idx === -1) return false;
                    var after = lh[idx + pattern.length];
                    return !after || after === '&' || after === '#';
                }}

                var links = document.querySelectorAll('a[href]');
                for (var variant of variants) {{
                    for (var l of links) {{
                        if (hrefMatchesSetlang(l.getAttribute('href') || '', variant)) {{
                            l.scrollIntoView({{block: 'center'}});
                            l.click();
                            return 'href_click[' + variant + ']:' + (l.href || '').substring(0, 80);
                        }}
                    }}
                }}

                // ── 调试输出：返回语言区块内元素信息 ──
                var section = document.querySelector('#language-section');
                if (section) {{
                    var sLinks = section.querySelectorAll('a, button, [role=button]');
                    var info = [];
                    for (var i = 0; i < Math.min(sLinks.length, 12); i++) {{
                        info.push('[' + sLinks[i].tagName + '] '
                            + (sLinks[i].textContent || '').trim().substring(0, 20)
                            + '|href=' + (sLinks[i].href || '').substring(0, 50));
                    }}
                    return 'debug_section:' + JSON.stringify(info);
                }}
                return 'debug_body:' + document.body.innerText.substring(0, 250).replace(/[\\n\\r]+/g, ' ');
            """)

            logger.info(f"{LogIndent.L2}[System] 语言切换JS结果: {str(clicked)[:300]}")

            if clicked and ('treewalker_click:' in str(clicked) or 'href_click[' in str(clicked)):
                time.sleep(random.uniform(3, 5))
                logger.success(f"{LogIndent.L2}[System] 语言已切换为 {lang_name}（DOM点击成功）")
                return True

            # ── 兜底：直接 GET setlang URL（服务端记录偏好），乐观返回 True ──
            logger.warning(f"{LogIcon.WARN} [System] DOM未命中，发送 setlang URL 参数请求...")
            direct_url = (
                f"https://www.bing.com/account/general"
                f"?setlang={variants[0]}"
                f"&ru=https%3A%2F%2Fwww.bing.com%2Frewards"
            )
            self.page.get(direct_url)
            time.sleep(random.uniform(2, 3))
            logger.info(f"{LogIndent.L2}[System] setlang 请求已发送，继续执行")
            return True

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} [System] 语言切换失败: {e}")
            return False

        """切换 Bing 账号的显示语言。
        lang: 'en' => 英语, 'zh' => 中文(简体)

        策略优先级：
          1. TreeWalker 深扫文本节点，向上寻找可点击父元素（覆盖 JS 渲染链接/按钮）
          2. 扫描所有 a[href] 中含 setlang 的链接
          3. 兜底：直接 GET setlang URL 参数（服务端保存偏好），乐观返回 True
        """
        setlang_map = {"en": "en-us", "zh": "zh-hans"}
        setlang = setlang_map.get(lang)
        if not setlang:
            logger.warning(f"{LogIcon.WARN} [System] 不支持的语言标识: {lang}")
            return False

        lang_name = "English" if lang == "en" else "中文(简体)"
        lang_url = (
            "https://www.bing.com/account/general"
            "?ru=https%3A%2F%2Fwww.bing.com%2Frewards"
            "&id=language_section#language-section"
        )
        try:
            logger.info(f"{LogIndent.L2}[System] 账号{account_index} 切换显示语言为: {lang_name}")
            self.page.get(lang_url)
            # 等待更长时间让 JS 渲染语言列表
            time.sleep(random.uniform(4, 6))

            # 滚动到底部再回顶，触发懒加载渲染
            try:
                self.page.scroll.to_bottom()
                time.sleep(1.5)
                self.page.scroll.to_top()
                time.sleep(1)
                sec = self.page.ele('#language-section', timeout=3)
                if sec:
                    self.page.scroll.to_see(sec)
                    time.sleep(1.5)
            except Exception:
                pass

            # --- 主策略：TreeWalker 深扫所有文本节点，找到 "English" 后向上查找可点击父元素 ---
            clicked = self.page.run_js(f"""
                var targetText = '{lang_name}';
                var targetLower = targetText.toLowerCase();
                var setlang = '{setlang}';

                // 判断元素是否可点击（a/button/role=button）
                function isClickable(el) {{
                    if (!el || !el.tagName) return false;
                    var tag = el.tagName.toUpperCase();
                    return tag === 'A' || tag === 'BUTTON' ||
                           el.getAttribute('role') === 'button' ||
                           typeof el.onclick === 'function' ||
                           el.getAttribute('onclick');
                }}

                // 从节点向上最多走 6 层找可点击父元素
                function findClickableAncestor(el) {{
                    for (var i = 0; i < 6; i++) {{
                        if (!el) break;
                        if (isClickable(el)) return el;
                        el = el.parentElement;
                    }}
                    return null;
                }}

                // 方法1：TreeWalker 遍历所有文本节点
                var walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null, false
                );
                var node;
                while (node = walker.nextNode()) {{
                    var t = (node.textContent || '').trim();
                    if (t.toLowerCase() === targetLower ||
                        (t.toLowerCase().includes(targetLower) && t.length < 40)) {{
                        var clickable = findClickableAncestor(node.parentElement);
                        if (clickable) {{
                            clickable.scrollIntoView({{block: 'center'}});
                            clickable.click();
                            return 'treewalker_click:' + t.substring(0, 30)
                                 + '|tag=' + clickable.tagName
                                 + '|href=' + (clickable.href || clickable.getAttribute('href') || '');
                        }}
                    }}
                }}

                // 方法2：href 中含 setlang 的 a 标签
                var links = document.querySelectorAll('a[href]');
                for (var l of links) {{
                    var href = (l.getAttribute('href') || '').toLowerCase();
                    if (href.includes('setlang=' + setlang) || href.includes('setlang')) {{
                        l.scrollIntoView({{block: 'center'}});
                        l.click();
                        return 'href_click:' + l.href;
                    }}
                }}

                // 调试：返回语言区块内的所有链接文本（帮助诊断页面结构）
                var section = document.querySelector('#language-section');
                if (section) {{
                    var sLinks = section.querySelectorAll('a, button, [role=button]');
                    var info = [];
                    for (var i = 0; i < Math.min(sLinks.length, 15); i++) {{
                        info.push('[' + sLinks[i].tagName + '] '
                            + (sLinks[i].textContent || '').trim().substring(0, 25)
                            + ' href=' + (sLinks[i].href || '').substring(0, 40));
                    }}
                    return 'debug_section:' + JSON.stringify(info);
                }}

                // 调试：返回页面正文前 300 字（判断页面是否正确加载）
                return 'debug_body:' + document.body.innerText.substring(0, 300)
                       .replace(/[\\n\\r]+/g, ' ');
            """)

            logger.info(f"{LogIndent.L2}[System] 语言切换JS结果: {str(clicked)[:250]}")

            if clicked and ('treewalker_click:' in str(clicked) or 'href_click:' in str(clicked)):
                time.sleep(random.uniform(3, 5))
                logger.success(f"{LogIndent.L2}[System] 语言已切换为 {lang_name}（DOM点击）")
                return True

            # --- 兜底：直接 GET setlang URL，服务端会读取并保存语言偏好 ---
            # 即使页面不跳转，Microsoft 服务端通常会处理 setlang 参数并记录到账号
            logger.warning(f"{LogIcon.WARN} [System] DOM方式未命中，发送 setlang URL 参数请求...")
            direct_url = (
                f"https://www.bing.com/account/general"
                f"?setlang={setlang}"
                f"&ru=https%3A%2F%2Fwww.bing.com%2Frewards"
            )
            self.page.get(direct_url)
            time.sleep(random.uniform(2, 3))
            # 无论是否跳转，都认为请求已发送，乐观继续
            logger.info(f"{LogIndent.L2}[System] setlang 请求已发送，继续执行 Earn 任务")
            return True

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} [System] 语言切换失败: {e}")
            return False

    # ===========================
    # 辅助：安全查找带任意引号的 href
    # ===========================
    def _safe_find_link(self, href, tab=None):
        """安全地通过 href 精确匹配 <a> 元素。
        普通情况使用 XPath；href 含双引号时自动切换到单引号包裹或 JS querySelector，
        避免 XPath 字符串嵌套双引号引发 SyntaxError。"""
        page = tab if tab else self.page
        try:
            if '"' not in href:
                # 最常见情况：href 无双引号，直接用双引号包裹的 XPath
                return page.ele(f'xpath://a[@href="{href}"]', timeout=3)
            elif "'" not in href:
                # href 含双引号但无单引号，改用单引号包裹的 XPath
                return page.ele(f"xpath://a[@href='{href}']", timeout=3)
            else:
                # href 同时含单、双引号（极少见），用 JS 精确匹配
                import json as _json
                href_js = _json.dumps(href)  # Python 会正确转义为合法 JS 字符串字面量
                result = page.run_js(f"""
                    var links = document.querySelectorAll('a[href]');
                    for (var l of links) {{
                        if (l.getAttribute('href') === {href_js}) return l;
                    }}
                    return null;
                """)
                return result if result else None
        except Exception:
            return None

    # ===========================
    # 清理
    # ===========================
    def cleanup(self):
        """清理资源"""
        try:
            if self.browser:
                self.browser.quit()
        except:
            pass
        try:
            if self.display:
                self.display.stop()
        except:
            pass
        logger.info(f"{LogIcon.CLEAN} {LogTag.SYSTEM} 浏览器和虚拟显示器已关闭")


# ===========================
# 主流程
# ===========================
def process_account(browser, account):
    """处理单个账号的完整登录流程"""
    idx = account["index"]
    username = account["username"]
    password = account["password"]
    cookie_key = account["cookie_key"]
    # 派生一个统一的 token_key 用于保存刷新令牌
    token_key = f"{cookie_key}_token"

    logger.info(f"{'='*50}")
    logger.info(f"{LogIcon.START} {LogTag.ACCOUNT} 开始处理账号 {idx}: {username[:3]}***{username[-10:]}")
    logger.info(f"{'='*50}")

    # 1. 尝试 Cookie 登录
    saved_cookie = get_cookie_from_local(cookie_key)
    if saved_cookie:
        if browser.login_with_cookie(saved_cookie, idx):
            # Cookie 有效，查询积分
            result = browser.get_rewards_points(idx)

            saved_token = get_cookie_from_local(token_key)
            if saved_token:
                logger.info(f"{LogIndent.L2}🔄 [Token] 尝试用本地缓存令牌刷新...")
                new_token_data = browser.get_access_token(saved_token)
                if new_token_data and new_token_data.get("refresh_token"):
                    saved_token = new_token_data["refresh_token"]
                    save_cookie_to_local(token_key, saved_token)
                    logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} [Token] 令牌刷新并缓存成功")
                else:
                    logger.warning(f"{LogIndent.L2}{LogIcon.WARN} [Token] 令牌刷新失败，将使用旧令牌尝试")
                
                app_sign = browser.complete_app_sign_in_task(saved_token, idx)
                read_progress = browser.complete_read_tasks(saved_token, idx)
                if result:
                    result["refresh_token"] = saved_token
                    result["read_progress"] = read_progress
                    result["app_sign_in"] = app_sign
            
            # 搜索任务
            search_done = browser.complete_search_tasks(idx)
            if result:
                result["search_done"] = search_done

            # latest_cookie = browser._get_cookie_string()
            # if latest_cookie:
            #     if result:
            #         save_cookie_to_local(cookie_key, latest_cookie)
            #     else:
            #         logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} 积分获取异常，跳过 Cookie 缓存")

            browser.complete_dashboard_tasks(idx)
            browser.complete_earn_page_tasks(idx)
            claimed_pts = browser.claim_dashboard_rewards(idx)
            if result:
                result["claimed_points"] = claimed_pts or 0
            
            # --- 任务执行完毕，重新获取最新积分以供结果汇总 ---
            latest_points = browser.get_rewards_points(idx, silent=True)
            if latest_points and result:
                result.update(latest_points)
                
            return result

        logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} Cookie 已失效，切换到密码登录")

    # 2. 密码登录
    if browser.login(username, password, idx):
        # 登录成功，查询积分
        result = browser.get_rewards_points(idx)
        # 获取刷新令牌
        token_result = browser.get_refresh_token(idx)
        if token_result:
            if result:
                save_cookie_to_local(token_key, token_result["refresh_token"])
                result["refresh_token"] = token_result["refresh_token"]
            else:
                logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} 积分获取异常，跳过 Token 缓存")
        
        # 保存 Cookie
        new_cookie = browser._get_cookie_string()
        if new_cookie:
            if result:
                save_cookie_to_local(cookie_key, new_cookie)
                logger.info(f"{LogIcon.COOKIE} {LogTag.COOKIE} Cookie 已保存 ({len(json.loads(new_cookie))} 个)")
            else:
                logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} 积分获取异常，跳过初始 Cookie 缓存")

        # --- 先保存凭证，持久化完成后，再执行额外的阅读任务 ---
        if token_result:
            app_sign = browser.complete_app_sign_in_task(token_result["refresh_token"], idx)
            read_pg = browser.complete_read_tasks(token_result["refresh_token"], idx)
            if result:
                result["read_progress"] = read_pg
                result["app_sign_in"] = app_sign
        else:
            saved_token = get_cookie_from_local(token_key)
            if saved_token:
                logger.info(f"{LogIndent.L2}🔄 [Token] 尝试用本地缓存令牌刷新...")
                new_token_data = browser.get_access_token(saved_token)
                if new_token_data and new_token_data.get("refresh_token"):
                    saved_token = new_token_data["refresh_token"]
                    save_cookie_to_local(token_key, saved_token)
                    logger.success(f"{LogIndent.L2}{LogIcon.SUCCESS} [Token] 令牌刷新并缓存成功")
                else:
                    logger.warning(f"{LogIndent.L2}{LogIcon.WARN} [Token] 令牌刷新失败，将使用旧令牌尝试")

                app_sign = browser.complete_app_sign_in_task(saved_token, idx)
                read_pg = browser.complete_read_tasks(saved_token, idx)
                if result:
                    result["refresh_token"] = saved_token
                    result["read_progress"] = read_pg
                    result["app_sign_in"] = app_sign
        
        # 搜索任务
        search_done = browser.complete_search_tasks(idx)
        if result:
            result["search_done"] = search_done

        latest_cookie = browser._get_cookie_string()
        if latest_cookie:
            if result:
                save_cookie_to_local(cookie_key, latest_cookie)
            else:
                logger.warning(f"{LogIcon.WARN} {LogTag.COOKIE} 积分获取异常，跳过后续 Cookie 缓存")

        browser.complete_dashboard_tasks(idx)
        browser.complete_earn_page_tasks(idx)
        claimed_pts = browser.claim_dashboard_rewards(idx)
        if result:
            result["claimed_points"] = claimed_pts or 0
        
        # --- 任务执行完毕，重新获取最新积分以供结果汇总 ---
        latest_points = browser.get_rewards_points(idx, silent=True)
        if latest_points and result:
            result.update(latest_points)
            
        return result
    else:
        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 账号 {idx} 登录失败")
        return None


def main():
    accounts = get_accounts()
    if not accounts:
        logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 未检测到有效的本地账号配置!")
        logger.info(f"{LogIcon.INFO} {LogTag.SYSTEM} 请在脚本同目录下创建 bing_accounts.json 文件")
        return

    logger.info(f"{LogIcon.START} {LogTag.SYSTEM} 检测到 {len(accounts)} 个账号")

    results = []

    for account in accounts:
        # 每个账号独立启动一个浏览器实例，确保完全清空前一账号 Cookie
        browser = BingRewardsBrowser()
        try:
            result = process_account(browser, account)
            results.append({
                "index": account["index"],
                "username": account["username"],
                "result": result,
            })

            # 多账号之间等待
            if account != accounts[-1]:
                wait_time = random.uniform(5, 10)
                logger.info(f"{LogTag.SYSTEM} 账号切换，等待 {wait_time:.1f}s...")
                time.sleep(wait_time)
        finally:
            # 单个账号执完毕后彻底关闭并清理该浏览器实例
            browser.cleanup()

    # 所有账号循环完毕，打印最终总结
    try:
        logger.info(f"\n{'='*50}")
        logger.info(f"{LogIcon.DATA} {LogTag.POINTS} 任务总结")
        logger.info(f"{'='*50}")
        for r in results:
            idx = r["index"]
            uname = r["username"][:3] + "***" + r["username"][-10:]
            if r["result"]:
                pts = r["result"].get("points", "?")
                lvl = r["result"].get("level", "")
                today = r["result"].get("today_points", "?")
                search = r["result"].get("search", {})
                remaining = search.get("remaining", "?")
                s_progress = search.get("progress", "?")
                s_max = search.get("max", "?")
                quests = r["result"].get("quests", {})
                acts = r["result"].get("activities", {})
                reads = r["result"].get("read_progress", 0)
                app_sign = r["result"].get("app_sign_in", -1)
                search_done = r["result"].get("search_done", 0)
                # logger.info(f"[Search] search_done={search_done}")
                
                app_sign_str = "今日已签到" if app_sign == 0 else (f"已完成({app_sign})" if app_sign > 0 else "失败")
                claimed = r["result"].get("claimed_points", 0)
                claim_str = f"已领取({claimed}分)" if claimed > 0 else "当前无"

                level_str = f" | {lvl}" if lvl else ""
                logger.success(f"✅ 账号{idx} ({r['username']}): {pts} 积分{level_str}")
                logger.info(f"{LogIndent.L2}├── 📊 今日积分: {today}分")
                logger.info(f"{LogIndent.L2}├── 🎁 积分领取: {claim_str}")
                logger.info(f"{LogIndent.L2}├── 📱 APP签到: {app_sign_str}")
                logger.info(f"{LogIndent.L2}├── 📖 APP阅读: {reads} 积分")
                logger.info(f"{LogIndent.L2}├── 🔍 搜索进度: {s_progress}/{s_max} (剩余{remaining}次)")
                logger.info(f"{LogIndent.L2}├── 📋 打卡任务: {quests.get('earned','?')}/{quests.get('total','?')} 分 ({quests.get('progress','?')}/{quests.get('max','?')})")
                logger.info(f"{LogIndent.L2}└── 🎯 继续赚取: {acts.get('earned','?')}/{acts.get('total','?')} ({acts.get('completed','?')}/{acts.get('all','?')})")
            else:
                logger.error(f"{LogIcon.FAIL} 账号{idx} ({uname}): 登录失败")

    except Exception as e:
        logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 脚本汇总阶段异常: {e}")


if __name__ == "__main__":
    main()