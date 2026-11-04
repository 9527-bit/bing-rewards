"""
实时登录调试脚本：启动本机 Chrome 窗口，直观排查登录过程中的 bug
"""

import sys
import time
import json
from bing_rewards.accounts import get_accounts, get_cookie_from_local
from bing_rewards.browser import BingRewardsBrowser
from bing_rewards.log import logger

def debug_account(account_index=1, use_cookie=True):
    accounts = get_accounts()
    if not accounts:
        logger.error("未找到账号配置，请检查 bing_accounts.json")
        return

    # 选取目标账号
    account = None
    for acc in accounts:
        if acc["index"] == account_index:
            account = acc
            break
    if not account:
        account = accounts[0]

    idx = account["index"]
    username = account["username"]
    password = account["password"]
    cookie_key = account["cookie_key"]

    logger.info(f"==================================================")
    logger.info(f"🔍 开始调试账号 {idx}: {username} (模式: {'使用Cookie' if use_cookie else '纯密码登录'})")
    logger.info(f"==================================================")

    browser = BingRewardsBrowser()
    try:
        page = browser.page
        logger.info(f"Chrome 已成功启动！当前页面: {page.url}")

        # 1. 测试 Cookie 登录
        if use_cookie:
            saved_cookie = get_cookie_from_local(cookie_key)
            if saved_cookie:
                logger.info("👉 检测到本地 Cookie，尝试进行 Cookie 注入登录...")
                cookie_success = browser.login_with_cookie(saved_cookie, idx)
                logger.info(f"Cookie 登录结果: {'✅ 成功' if cookie_success else '❌ 失败'}")
                logger.info(f"当前页面 URL: {page.url}")
                logger.info(f"当前页面 Title: {page.title}")

                if cookie_success:
                    logger.info("🎉 Cookie 登录通过，正在验证 Rewards 页面...")
                    points = browser.get_rewards_points(idx)
                    logger.info(f"获取积分结果: {points}")
                    logger.info("调试结束，浏览器将保持 10 秒供你查看...")
                    time.sleep(10)
                    return
                else:
                    logger.warning("Cookie 登录验证未通过，将继续测试密码登录...")
                    time.sleep(3)
            else:
                logger.info("本地无该账号 Cookie 缓存，直接进入密码登录测试...")
        else:
            logger.info("🚫 已指定 --no-cookie，跳过本地 Cookie 注入，直接进入纯账号密码登录测试...")

        # 2. 测试密码登录
        logger.info("👉 开始测试账号密码登录流程...")
        # 详细诊断：如果卡住，打印当前页面的所有文字和按钮
        try:
            login_success = browser.login(username, password, idx)
        except Exception as le:
            logger.error(f"login 抛出异常: {le}")
            login_success = False

        logger.info(f"密码登录结果: {'✅ 成功' if login_success else '❌ 失败'}")
        logger.info(f"当前页面 URL: {page.url}")
        logger.info(f"当前页面 Title: {page.title}")

        # 诊断当前页面结构
        try:
            page_text = page.run_js("return document.body.innerText") or ""
            logger.info(f"📋 当前页面文本概要:\n{page_text[:500]}")
            buttons = page.run_js("""
                return Array.from(document.querySelectorAll('button, a, input[type=submit], div[role=button], [tabindex="0"]'))
                    .map(el => (el.innerText || el.value || el.id || el.className || '').trim())
                    .filter(t => t.length > 0 && t.length < 50);
            """)
            logger.info(f"🔘 当前页面可点击按钮/选项: {buttons}")
        except Exception as pe:
            logger.warning(f"获取页面元素失败: {pe}")

        if not login_success:
            logger.error("❌ 登录未成功，请观察当前桌面上打开的 Chrome 界面！")
            logger.info("浏览器将保持开启 30 秒供你人工观察排查...")
            time.sleep(30)
        else:
            logger.info("🎉 密码登录成功！正在保存新鲜 Cookie 到 bing_cookies.json...")
            from bing_rewards.accounts import save_cookie_to_local
            new_cookie = browser._get_cookie_string()
            if new_cookie:
                save_cookie_to_local(cookie_key, new_cookie)
                logger.info("✅ 新鲜 Cookie 已持久化保存！")

            logger.info("正在获取积分数据...")
            points = browser.get_rewards_points(idx)
            logger.info(f"获取积分结果: {points}")
            time.sleep(10)

    except Exception as e:
        logger.error(f"调试过程发生异常: {e}", exc_info=True)
        time.sleep(15)
    finally:
        browser.cleanup()
        logger.info("浏览器已关闭，调试结束。")

if __name__ == "__main__":
    args = sys.argv[1:]
    no_cookie = "--no-cookie" in args
    clean_args = [a for a in args if not a.startswith("--")]
    acc_idx = int(clean_args[0]) if clean_args else 1
    debug_account(acc_idx, use_cookie=not no_cookie)
