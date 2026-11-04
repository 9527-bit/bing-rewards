"""
ReadTasksMixin：OAuth 令牌管理、阅读任务、APP 签到
"""

import json
import time
import random
import secrets
import requests
from urllib.parse import urlparse, parse_qs

from .config import (
    OAUTH_CLIENT_ID, OAUTH_REDIRECT_URI, OAUTH_SCOPE,
    OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL,
)
from .log import logger, LogTag, LogIcon, LogIndent
from .utils import retry_decorator


class ReadTasksMixin:
    """阅读/签到/OAuth 令牌 Mixin"""

    # ===========================
    # OAuth 刷新令牌获取
    # ===========================
    def get_refresh_token(self, account_index=1):
        """登录成功后，通过 OAuth 流程获取 refresh_token"""
        logger.info(f"{LogIcon.KEY} {LogTag.LOGIN} 账号{account_index} 开始获取刷新令牌...")

        try:
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
            token_data = {
                "client_id": OAUTH_CLIENT_ID,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": OAUTH_REDIRECT_URI,
                "scope": OAUTH_SCOPE,
            }

            resp = requests.post(OAUTH_TOKEN_URL, data=token_data, timeout=15)

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

            return {
                "refresh_token": refresh_token,
                "access_token": access_token,
            }

        except Exception as e:
            logger.error(f"{LogIcon.FAIL} {LogTag.LOGIN} 获取刷新令牌异常: {e}")
            return None

    # ===========================
    # 令牌刷新
    # ===========================
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

    # ===========================
    # 阅读进度
    # ===========================
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

    # ===========================
    # APP 签到
    # ===========================
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

    # ===========================
    # 阅读任务提交
    # ===========================
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
