"""
AuthMixin：Microsoft 登录流程（密码登录、Cookie 登录、登录验证）
"""

import json
import time
import random

from .config import BING_URL, REWARDS_URL, REWARDS_SIGNIN_URL
from .log import logger, LogTag, LogIcon, LogIndent
from .utils import retry_decorator


class AuthMixin:
    """登录功能 Mixin：密码登录、Cookie 登录、验证登录状态"""

    # ===========================
    # Microsoft 登录流程
    # ===========================
    def _dismiss_messages(self):
        """尝试关闭各种弹窗和消息"""
        # 1. 优先检测并跳过各类安全中断页（如 credentialaction "暂时跳过"、关闭按钮）
        skip_selectors = [
            'tag:button@@text()=暂时跳过',
            'tag:button@@text()=以后再说',
            'tag:button@@text()=跳过',
            'tag:button@@text()=Skip for now',
            'tag:button@@text()=Skip',
            '#close-button',
            'button[aria-label="关闭"]',
            'button[aria-label="Close"]',
        ]
        for sel in skip_selectors:
            try:
                btn = self.page.ele(sel, timeout=0.1)
                if btn:
                    btn.click()
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击跳过/关闭按钮: {sel}")
                    time.sleep(1.5)
                    return True
            except:
                continue

        # 2. Microsoft 登录过程中常见的弹窗按钮 ID 列表
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
                btn = self.page.ele(sel, timeout=0.1)
                if btn:
                    btn.click()
                    time.sleep(1)
                    return True
            except:
                continue

        # 通行密钥 (Passkey) / FIDO 中断取消处理
        try:
            cancel_result = self.page.run_js('''
                var btns = document.querySelectorAll('button[data-testid="secondaryButton"], button, a');
                for (var b of btns) {
                    var t = (b.innerText || '').trim();
                    if (t === '取消' || t === '以后再说' || t === '跳过' || t === 'Cancel' || t === 'Skip' || b.getAttribute('data-testid') === 'secondaryButton') {
                        b.click();
                        return t || 'secondaryButton';
                    }
                }
                return null;
            ''')
            if cancel_result:
                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已自动跳过弹窗/取消通行密钥设置 ({cancel_result})")
                time.sleep(2)
                return True
        except Exception:
            pass

        return False

    def _wait_for_login_redirect(self, timeout=30):
        """等待登录后跳转回 bing.com 或 rewards.bing.com"""
        for i in range(timeout):
            time.sleep(1)
            current_url = self.page.url or ""
            # 已经到达 Rewards 页面或 Bing 首页（通过 URL 前缀严格判断，防止 login.live.com 的 redirect_uri 参数误判）
            is_on_rewards = (
                current_url.startswith("https://rewards.bing.com")
                and "Signin" not in current_url
                and "signin-oidc" not in current_url
            )
            is_on_bing = (
                (current_url.startswith("https://www.bing.com") or current_url.startswith("https://cn.bing.com"))
                and not any(k in current_url for k in ["login.live.com", "microsoftonline.com", "login.microsoft.com", "account.live.com"])
            )
            if is_on_rewards or is_on_bing:
                return True

            # 快速异常状态检测（如拦截、密码错误、锁定等），及时止损
            page_text = self.page.html or ""
            if "此密码不是你的" in page_text or "密码不正确" in page_text:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 密码错误：此密码不是该 Microsoft 账户的正确密码，请核对 bing_accounts.json")
                return False
            if "帮助我们保护你的帐户" in page_text or "检测到异常登录" in page_text:
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 微软异地/新设备安全拦截：检测到异常登录，需要邮箱/手机验证码 (2FA)")
                return False
            if "已被锁定" in page_text or "locked" in page_text.lower():
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 账号已被微软锁定")
                return False

            # 处理保持登录状态 (KMSI) 弹窗
            self._handle_stay_signed_in()

            # 处理中断页及中间弹窗
            self._dismiss_messages()

        return False

    @retry_decorator(retries=2)
    def login(self, username, password, account_index=1):
        """使用账号密码登录 Microsoft Rewards"""
        logger.info(f"{LogIcon.KEY} {LogTag.LOGIN} 账号{account_index} 开始登录流程...")
        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 邮箱: {username[:3]}***{username[-10:]}")

        try:
            # === 第一步：直接访问 Microsoft Rewards 统一登录入口 ===
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 正在访问 Microsoft 登录入口...")
            self.page.get(REWARDS_SIGNIN_URL)
            time.sleep(random.uniform(2, 3))

            # 等待 Microsoft 登录页面加载完成
            for wait in range(15):
                current_url = self.page.url or ""
                # 如果已经到达 Microsoft 登录页
                if "login.live.com" in current_url or "login.microsoftonline.com" in current_url or "account.live.com" in current_url:
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已到达 Microsoft 登录页")
                    break

                # 检查输入框是否已出现
                if self.page.ele("#usernameEntry", timeout=0.1) or self.page.ele("#i0116", timeout=0.1):
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 登录输入框已就绪")
                    break

                # 检查是否已处于有效登录状态（直达 rewards 仪表盘，且不在 Signin 触发页）
                if current_url.startswith("https://rewards.bing.com") and "Signin" not in current_url and "signin-oidc" not in current_url:
                    logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 已处于登录状态")
                    return True

                time.sleep(1)
            else:
                # 兜底：如果网络跳转异常，尝试通过 Bing 首页登录按钮进入
                logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 直连登录入口未跳转，尝试从 Bing 首页进入...")
                self.page.get(BING_URL)
                time.sleep(2)
                login_btn = self.page.ele('#id_l', timeout=2)
                if login_btn:
                    login_btn.click()
                    time.sleep(3)

                # 严格检测页面中是否确实存在已登录用户的头像/昵称元素（严禁整个 HTML 字符串匹配 "id_p"）
                if self.page.ele('#id_n', timeout=1) or self.page.ele('a[id*="id_p"]', timeout=1):
                    logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 已处于登录状态")
                    return True

                current_url = self.page.url or ""
                if not ("login.live.com" in current_url or "login.microsoftonline.com" in current_url):
                    logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 未正常展开登录页面，当前: {current_url}")
                    return False

            time.sleep(1)

            # === 第二步：输入邮箱 ===
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 输入邮箱...")
            # 新版 Fluent UI 用 #usernameEntry，旧版用 #i0116
            email_input = self.page.ele("#usernameEntry", timeout=5)
            if not email_input:
                email_input = self.page.ele("#i0116", timeout=3)

            if not email_input:
                # 检查是否已直接处于密码页或已被微软识别账号进入验证选择页
                if self._find_password_input(timeout=1):
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 页面已识别账号并处于密码输入页，跳过输入邮箱")
                else:
                    logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 未找到邮箱输入框，检测是否处于已识别账号的中间选择页...")
                    self._handle_intermediate_pages()
                    # 再次检查是否顺利切入密码页
                    if not self._find_password_input(timeout=3):
                        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 未找到邮箱输入框，也未进入密码页")
                        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 当前URL: {self.page.url}")
                        logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 页面标题: {self.page.title}")
                        return False
            else:
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
                self._handle_intermediate_pages()

            # === 第四步：输入密码 ===
            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 输入密码...")
            # 等待真正的密码输入框出现（避免把"使用密码"选项误判为输入框）
            password_input = self._wait_for_password_input(timeout=35)
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
            if self._wait_for_login_redirect(timeout=30):
                # 同步访问一次 Rewards 页面以完成 SSO 握手并写入 rewards.bing.com 域 Cookie
                try:
                    self.page.get(REWARDS_URL)
                    time.sleep(3)
                except Exception:
                    pass
                logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 登录成功!")
                return True
            else:
                # 只有真正停留在 rewards.bing.com 域且不在授权发起/重定向路径上，才认定为登录成功
                current_url = self.page.url or ""
                if current_url.startswith("https://rewards.bing.com") and "Signin" not in current_url and "signin-oidc" not in current_url:
                    logger.success(f"{LogIcon.SUCCESS} {LogTag.LOGIN} 账号{account_index} 登录成功!")
                    return True
                logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 登录未成功，当前URL: {current_url}")
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

    def _wait_for_password_input(self, timeout=35):
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

    def _handle_fido_bridge(self):
        """检测并跳过通行密钥桥接页 (login.microsoft.com/.../bridge/fido)，彻底规避 Windows Hello 弹窗拦截"""
        try:
            current_url = self.page.url or ""
            current_title = self.page.title or ""
            if "bridge/fido" in current_url or "通行密钥" in current_title or "fido" in current_url.lower():
                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 检测到通行密钥拦截页 (bridge/fido)，正在取消...")
                # 方案1：通过 JS 点击 close-button 或 取消按钮
                try:
                    closed = self.page.run_js('''
                        var btn = document.getElementById("close-button") || 
                                  document.querySelector('[id*="close"], button[aria-label="关闭"], button[aria-label="Close"], button');
                        if (btn) { btn.click(); return true; }
                        return false;
                    ''')
                    if closed:
                        time.sleep(2)
                except Exception:
                    pass

                # 方案2：如果仍在 bridge/fido 页面，直接从 URL 中提取 cancelUrl 重定向
                current_url = self.page.url or ""
                if "bridge/fido" in current_url and "cancelUrl=" in current_url:
                    from urllib.parse import urlparse, parse_qs, unquote
                    try:
                        parsed = urlparse(current_url)
                        params = parse_qs(parsed.query)
                        if "cancelUrl" in params:
                            cancel_url = unquote(params["cancelUrl"][0])
                            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 通过 cancelUrl 自动跳过通行密钥...")
                            self.page.get(cancel_url)
                            time.sleep(3)
                            return True
                    except Exception:
                        pass
                return True
        except Exception:
            pass
        return False

    def _handle_intermediate_pages(self):
        """处理登录过程中可能出现的中间页面（验证方式选择、账号类型选择等）"""
        time.sleep(1)

        # 优先检测并取消通行密钥桥接页
        self._handle_fido_bridge()

        # === 场景1：验证方式选择页面（新版 Fluent UI） ===
        # 输入邮箱后，Microsoft 可能显示多种验证方式：
        # - 发送请求（Authenticator 通知）
        # - 使用人脸、指纹、PIN 或安全密钥
        # - 使用密码
        # 需要依次处理"其他登录方法" -> "显示更多选项" -> "使用密码"
        try:
            # 已经在密码输入页则直接返回
            if self._find_password_input(timeout=0.3):
                return

            # 1. 检查是否出现"其他登录方法" / "其他登录方式"
            for text in ["其他登录方法", "其他登录方式", "Other ways to sign in"]:
                try:
                    other_btn = self.page.ele(f'text:{text}', timeout=0.5)
                    if other_btn:
                        other_btn.click(by_js=True)
                        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击「{text}」")
                        time.sleep(1.5)
                        break
                except Exception:
                    pass

            # 2. 检查是否出现"显示更多选项"
            for text in ["显示更多选项", "Show more options"]:
                try:
                    show_more = self.page.ele(f'text:{text}', timeout=0.5)
                    if show_more:
                        show_more.click(by_js=True)
                        logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已点击「{text}」")
                        time.sleep(1.5)
                        break
                except Exception:
                    pass

            page_text = self.page.html or ""
            page_text_lower = page_text.lower()
            # 检测是否在验证方式选择页面
            if (
                "验证" in page_text
                or "使用另一种方式登录" in page_text
                or "获取登录请求" in page_text
                or "获取用于登录的代码" in page_text
                or "verify" in page_text_lower
                or "credential" in page_text_lower
                or "show more options" in page_text_lower
                or "passwordEntry" in page_text
                or "tile" in page_text
            ):
                # 方式1：原生 CDP 点击「使用密码」文本或 tile（最可靠，能完整触发 React 事件监听）
                for pwd_text in ["使用密码", "使用你的密码", "Use your password", "Use a password"]:
                    try:
                        pwd_opt = self.page.ele(f'text:{pwd_text}', timeout=0.4) or self.page.ele(f'css:[data-testid="tile"]@@text():{pwd_text}', timeout=0.4)
                        if pwd_opt:
                            pwd_opt.click()
                            time.sleep(1.5)
                            if self._find_password_input(timeout=3):
                                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已选择「{pwd_text}」验证方式 (原生点击)")
                                return
                    except Exception:
                        pass

                # 方式2：通过 JS 派发带冒泡机制的完整 MouseEvent
                try:
                    result = self.page.run_js("""
                        var candidates = document.querySelectorAll(
                            '[data-testid="tile"], [data-testid="credential-picker-password"], [data-testid="passwordEntry"], #idA_PWD_SwitchToPassword, button, a, div[role="button"], span'
                        );
                        for (var el of candidates) {
                            var text = (el.innerText || el.textContent || '').trim();
                            var lower = text.toLowerCase();
                            if (!text) continue;
                            if (text === '使用密码' || text === '使用你的密码' || lower === 'use a password' || lower === 'use your password' || lower === 'password') {
                                el.scrollIntoView({block: 'center'});
                                el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                                return text.substring(0, 40);
                            }
                        }
                        return null;
                    """)
                    if result:
                        time.sleep(1.5)
                        if self._find_password_input(timeout=3):
                            logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已通过JS选择「使用密码」验证方式: {result.strip()}")
                            return
                except:
                    pass

                # 方式3：通过 JS 辅助查找选择器点击
                exact_selector = 'css:[data-testid="tile"], [data-testid="credential-picker-password"], [data-testid="passwordEntry"], #idA_PWD_SwitchToPassword'
                tiles = self.page.eles(exact_selector, timeout=1)
                for t in tiles:
                    try:
                        txt = (t.text or '').strip()
                        if txt in ["使用密码", "使用你的密码", "Use your password", "Use a password"]:
                            t.click(by_js=True)
                            time.sleep(1.5)
                            if self._find_password_input(timeout=3):
                                logger.info(f"{LogIndent.L2}{LogTag.LOGIN} 已选择「{txt}」验证方式 (选择器命中)")
                                return
                            break
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"{LogIcon.WARN} {LogTag.LOGIN} 处理中间选择页异常: {e}")

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
