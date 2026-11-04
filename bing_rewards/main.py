"""
主流程编排：process_account（单账号完整流程）、main（多账号循环 + 结果汇总）
"""

import json
import time
import random

from .log import logger, LogTag, LogIcon, LogIndent
from .accounts import get_accounts, get_cookie_from_local, save_cookie_to_local
from .browser import BingRewardsBrowser


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

            # 视觉搜索打卡
            visual_done = browser.complete_visual_search_task(idx)
            if result:
                result["visual_search_done"] = visual_done

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
        # 保存 Cookie 与 Token
        new_cookie = browser._get_cookie_string()
        if new_cookie:
            save_cookie_to_local(cookie_key, new_cookie)
            logger.info(f"{LogIcon.COOKIE} {LogTag.COOKIE} Cookie 已保存 ({len(json.loads(new_cookie))} 个)")

        # 获取刷新令牌
        token_result = browser.get_refresh_token(idx)
        if token_result:
            save_cookie_to_local(token_key, token_result["refresh_token"])
            if result:
                result["refresh_token"] = token_result["refresh_token"]

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

        # 视觉搜索打卡
        visual_done = browser.complete_visual_search_task(idx)
        if result:
            result["visual_search_done"] = visual_done

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
                vs_done = r["result"].get("visual_search_done", False)
                vs_str = "已完成" if vs_done else "已跳过/无任务"
                logger.info(f"{LogIndent.L2}├── 📸 视觉搜索: {vs_str}")
                logger.info(f"{LogIndent.L2}├── 📋 打卡任务: {quests.get('earned','?')}/{quests.get('total','?')} 分 ({quests.get('progress','?')}/{quests.get('max','?')})")
                logger.info(f"{LogIndent.L2}└── 🎯 继续赚取: {acts.get('earned','?')}/{acts.get('total','?')} ({acts.get('completed','?')}/{acts.get('all','?')})")
            else:
                logger.error(f"{LogIcon.FAIL} 账号{idx} ({uname}): 登录失败")

    except Exception as e:
        logger.error(f"{LogIcon.FAIL} {LogTag.SYSTEM} 脚本汇总阶段异常: {e}")
