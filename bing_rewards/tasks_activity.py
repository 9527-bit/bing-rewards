"""
ActivityTasksMixin：Dashboard 每日卡片、积分领取、Earn 页面任务（含 Quiz/Quest）、显示语言切换
"""

import time
import random
import re
import json

from .config import (
    REWARDS_URL,
    REWARDS_EARN_URL,
    BING_ACCOUNT_GENERAL_URL,
    BING_ACCOUNT_LANGUAGE_URL,
)
from .log import logger, LogIcon, LogIndent


class ActivityTasksMixin:
    """活动任务 Mixin：Dashboard 卡片、积分领取、Earn 页面点击任务、语言切换"""

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
            self.page.get(REWARDS_URL)
            self.page.wait.load_start()
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
            self.page.get(REWARDS_EARN_URL)
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
            self.page.get(REWARDS_EARN_URL)
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

        lang_url = BING_ACCOUNT_LANGUAGE_URL
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
            variants_js   = json.dumps([v.lower() for v in variants])
            text_names_js = json.dumps(textNames)

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
                f"{BING_ACCOUNT_GENERAL_URL}"
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
