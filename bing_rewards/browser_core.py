"""
BrowserCoreMixin：浏览器初始化、清理、Cookie 管理、辅助方法
"""

import os
import sys
import json
import requests

from .config import VERSION, RE_NEXT_ACTION
from .log import logger, LogTag, LogIcon, LogIndent, HAS_DISPLAY, Display

# 清理 DISPLAY 环境变量（避免干扰虚拟显示器）
os.environ.pop("DISPLAY", None)


class BrowserCoreMixin:
    """浏览器核心功能 Mixin：初始化、Cookie 管理、辅助方法、资源清理"""

    @staticmethod
    def _create_chromium_options(headless=False):
        """创建独立的 Chromium 配置对象，配置专用独立目录与空闲端口"""
        import socket
        from DrissionPage import ChromiumOptions

        co = ChromiumOptions()

        # 端口自适应：首选 9222，若被占用或残留则依次尝试 9223~9225
        preferred_port = 9222
        for port_candidate in [9222, 9223, 9224, 9225]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex(('127.0.0.1', port_candidate)) != 0:
                        preferred_port = port_candidate
                        break
            except Exception:
                pass
        co.set_address(f'127.0.0.1:{preferred_port}')

        # 独立的数据目录：存放在项目根目录下的 browser_profile，彻底隔离系统默认目录与锁冲突
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profile_dir = os.path.join(root_dir, "browser_profile")
        os.makedirs(profile_dir, exist_ok=True)
        co.set_user_data_path(profile_dir)

        if headless:
            co.headless(True)
        else:
            co.headless(False)

        co.incognito(True)
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        co.set_argument("--disable-dev-shm-usage")
        co.set_argument("--window-size=1920,1080")
        co.set_argument("--mute-audio")
        co.set_argument("--lang=zh-CN")
        co.set_argument("--accept-lang=zh-CN,zh;q=0.9")
        co.set_pref("intl.accept_languages", "zh-CN,zh")
        co.set_argument("--disable-password-manager-reauthentication")
        co.set_argument("--remote-debugging-address=127.0.0.1")
        co.set_argument("--disable-features=WebAuthentication,WebAuthenticationConditionalUI,WebAuthenticationNewPasskeyUI,WebAuthenticationPermitEnterpriseAttestation,WebAuthenticationPasskeyUpgrade,WebAuthenticationCable")

        # 自动路径探测（Mac、Linux 与 Windows）
        if os.path.exists("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
            co.set_browser_path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        elif os.path.exists("/usr/bin/chromium"):
            co.set_browser_path("/usr/bin/chromium")
        elif os.path.exists("/usr/bin/chromium-browser"):
            co.set_browser_path("/usr/bin/chromium-browser")
        elif os.path.exists("/usr/bin/google-chrome"):
            co.set_browser_path("/usr/bin/google-chrome")
        elif sys.platform.startswith("win"):
            win_candidates = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]
            for cand in win_candidates:
                if os.path.isfile(cand):
                    co.set_browser_path(cand)
                    break

        return co

    def __init__(self):
        self.display = None
        self.browser = None
        self.page = None
        self._last_rsc_data = ""  # 缓存 /earn 页面 RSC 数据，供 quest 解析复用
        logger.info(f"{LogIcon.START} 启动 Bing Rewards 自动化脚本 (版本: {VERSION})...")

        # 1. 启动虚拟显示器（仅在 Linux 环境下启动，Windows 和 Mac 跳过）
        if HAS_DISPLAY and sys.platform.startswith("linux"):
            try:
                self.display = Display(visible=0, size=(1920, 1080))
                self.display.start()
                logger.info(f"{LogTag.SYSTEM} 虚拟显示器启动成功")
            except Exception as e:
                logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 虚拟显示器启动失败: {e}")

        # 2. 配置 Chromium
        from DrissionPage import Chromium

        is_headless = os.getenv("HEADLESS", "").lower() in ("1", "true", "yes") or any("headless" in str(arg).lower() for arg in sys.argv)
        if is_headless:
            logger.info(f"{LogTag.SYSTEM} 检测到无头模式参数，启用 Headless...")

        try:
            co = self._create_chromium_options(headless=is_headless)
            self.browser = Chromium(co)
        except Exception as e:
            # 如果是有界面模式启动失败（如无界面 Windows Server 或计划任务锁屏），自动降级为无头模式自愈
            if not is_headless:
                logger.warning(f"{LogIcon.WARN} {LogTag.SYSTEM} 界面模式启动异常: {e}")
                logger.info(f"{LogTag.SYSTEM} 正在自动切换为无头模式 (Headless) 自愈重试...")
                try:
                    co_headless = self._create_chromium_options(headless=True)
                    self.browser = Chromium(co_headless)
                    logger.success(f"{LogTag.SYSTEM} 无头模式自愈启动成功！")
                except Exception as e2:
                    logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 浏览器启动彻底失败: {e2}")
                    if self.display:
                        self.display.stop()
                    sys.exit(1)
            else:
                logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 浏览器启动失败: {e}")
                if self.display:
                    self.display.stop()
                sys.exit(1)

        self.page = self.browser.latest_tab
        # 全局注入：拒绝 WebAuthn 硬件密钥请求（同时拦截登录 get 与注册 create），彻底避免 Windows Hello 弹窗
        try:
            self.page.run_cdp('Page.addScriptToEvaluateOnNewDocument', source='''
                if (window.navigator) {
                    try { window.PublicKeyCredential = undefined; } catch(e) {}
                    if (window.navigator.credentials) {
                        window.navigator.credentials.get = function() {
                            return Promise.reject(new DOMException("NotAllowedError", "NotAllowedError"));
                        };
                        window.navigator.credentials.create = function() {
                            return Promise.reject(new DOMException("NotAllowedError", "NotAllowedError"));
                        };
                    }
                }
            ''')
        except Exception:
            pass
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
        """清理资源，强制杀掉所有子进程并清理临时数据，防止后台残留僵尸进程"""
        try:
            if self.browser:
                self.browser.quit(timeout=3, force=True, del_data=True)
        except:
            pass
        try:
            if self.display:
                self.display.stop()
        except:
            pass
        logger.info(f"{LogIcon.CLEAN} {LogTag.SYSTEM} 浏览器和虚拟显示器已关闭")
