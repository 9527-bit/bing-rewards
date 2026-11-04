"""
PointsMixin：从 /earn 页面获取积分、解析连胜、活动卡片
"""

import json
import re
import time
import requests

from .config import REWARDS_EARN_URL
from .log import logger, LogTag, LogIcon, LogIndent
from .utils import get_pinzan_proxy


class PointsMixin:
    """积分解析 Mixin：从 /earn 页面获取积分详情"""

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
                                        
                                        # 2. 判断是否弹出包含"退出"的卡片，确认是登录状态
                                        logout_text = self.page.ele('text:退出', timeout=2)
                                        if logout_text:
                                            if not silent:
                                                logger.info(f"{LogIndent.L2}{LogIcon.INFO} [Points] 确认处于登录态，准备点击加入商城...")
                                            
                                            # 点击页面空白处收起白色卡片，防止遮挡中间的加入按钮
                                            self.page.run_js('document.body.click();')
                                            time.sleep(1)
                                            
                                            # 3. 寻找并点击蓝色的大按钮"加入微软积分商城"
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
                m_points = re.search(r'\[\s*(?:"|\\")\\+(?:"|\\\")\s*,\s*(?:"|\\")(\d+)(?:"|\\\")\s*\]', quest_section)
                if not m_points:
                    # 备用匹配，寻找带有 +号和数字的结构
                    m_points = re.search(r'(?:"|\\")\\+(?:"|\\")[^\d]*?(\d+)', quest_section)
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
                r'(?:"|\\")MoreActivities(?:"|\\").{0,1500}?(?:"|\\")activityCards(?:"|\\\")\s*:\s*\[',
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

                    c = re.search(r'"isCompleted"\s*:\s*(true|false|(?:"|\\")true(?:"|\\\")|(?:"|\\")false(?:"|\\"))', segment)
                    p = re.search(r'"points"\s*:\s*(-?\d+)', segment)
                    u = re.search(r'"isUnlocked"\s*:\s*(true|false|(?:"|\\")true(?:"|\\\")|(?:"|\\")false(?:"|\\\")|(?:"|\\\")\\$undefined(?:"|\\\")|"\\$undefined")', segment)
                    promo = re.search(r'"isPromotional"\s*:\s*(true|false|(?:"|\\")true(?:"|\\\")|(?:"|\\")false(?:"|\\\")|(?:"|\\\")\\$undefined(?:"|\\\")|"\\$undefined")', segment)

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
