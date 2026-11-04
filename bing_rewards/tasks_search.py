import os
import time
import random
import base64
from pathlib import Path
from urllib.parse import quote
import requests

from .config import SEARCH_HOME_CN_URL, SEARCH_REQUEST_URL
from .log import logger, LogTag, LogIcon, LogIndent
from .hot_words import hot_words_manager


class SearchTasksMixin:
    """搜索任务 Mixin：按剩余进度执行模拟搜索及视觉搜索打卡"""

    # ===========================
    # 搜索任务
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

    # ===========================
    # 视觉搜索任务 (Visual Search)
    # ===========================
    def _ensure_visual_search_image(self) -> str:
        """确保本地存在用于视觉搜索的图片，不存在则自动下载或生成"""
        project_root = Path(__file__).parent.parent
        img_path = project_root / "visual_search.jpg"

        if img_path.exists() and img_path.stat().st_size > 1000:
            return str(img_path)

        logger.info(f"{LogIndent.L2}📷 正在准备视觉搜索图片素材...")
        # 1. 优先从微软必应壁纸官方接口获取一张高清图片（国内/海外均秒级加载）
        try:
            api_url = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(api_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                rel_url = data.get("images", [{}])[0].get("url", "")
                if rel_url:
                    full_url = f"https://cn.bing.com{rel_url}" if rel_url.startswith("/") else rel_url
                    img_data = requests.get(full_url, headers=headers, timeout=8).content
                    if len(img_data) > 1000:
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        logger.success(f"{LogIndent.L2}✅ 必应壁纸图片已获取并缓存 ({img_path.name}, 大小: {len(img_data)//1024}KB)")
                        return str(img_path)
        except Exception as e:
            logger.warning(f"{LogIndent.L2}⚠️ 获取必应壁纸图片失败: {e}，尝试生成备用图片")

        # 2. 兜底：内置有效 JPEG
        try:
            fallback_b64 = (
                "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
                "wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
            )
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(fallback_b64))
            logger.info(f"{LogIndent.L2}ℹ️ 已使用内置备用图片 ({img_path.name})")
            return str(img_path)
        except Exception:
            pass

        return str(img_path)

    def complete_visual_search_task(self, account_index=1) -> bool:
        """执行必应视觉搜索（Visual Search）打卡任务"""
        logger.info(f"{LogIcon.SEARCH} [VisualSearch] 账号{account_index} 准备执行视觉搜索任务...")

        img_path = self._ensure_visual_search_image()
        if not os.path.exists(img_path) or os.path.getsize(img_path) < 100:
            logger.warning(f"{LogIndent.L2}❌ 未找到可用图片，跳过视觉搜索任务")
            return False

        try:
            # 注入国际化 Cookie
            try:
                self.page.set.cookies({'name': 'ENSEARCH', 'value': '1', 'domain': '.bing.com', 'path': '/'})
                self.page.set.cookies({'name': '_EDGE_S', 'value': 'mkt=en-us', 'domain': '.bing.com', 'path': '/'})
            except Exception:
                pass

            file_input = None
            selectors = ['#sb_fileinput', 'tag:input@type=file', 'css:input[type="file"]', 'css:input.fileinput']

            # 1. 首选策略：访问必应图片主页 https://www.bing.com/images（最稳定、全局可用、直接内置 #sb_fileinput 上传控件）
            logger.info(f"{LogIndent.L2}🌐 打开必应图片主页 (bing.com/images)...")
            self.page.get("https://www.bing.com/images")
            time.sleep(2)

            for sel in selectors:
                try:
                    inp = self.page.ele(sel, timeout=3)
                    if inp:
                        file_input = inp
                        break
                except Exception:
                    pass

            # 2. 次选策略：访问视觉搜索直达页 https://www.bing.com/visualsearch
            if not file_input:
                logger.info(f"{LogIndent.L2}🌐 尝试视觉搜索直达页 (bing.com/visualsearch)...")
                self.page.get("https://www.bing.com/visualsearch")
                time.sleep(2)
                for sel in selectors:
                    try:
                        inp = self.page.ele(sel, timeout=3)
                        if inp:
                            file_input = inp
                            break
                    except Exception:
                        pass

            # 3. 兜底策略：访问搜索主页并点击相机图标激活控件
            if not file_input:
                logger.info(f"{LogIndent.L2}🌐 尝试主页相机入口 (bing.com/?cc=us)...")
                self.page.get("https://www.bing.com/?cc=us&setlang=en")
                time.sleep(2)
                for cam_sel in ['.camera.icon', '#sb_cam_island', '#sb_form > div.camera.icon', '#sb_sbi', '@aria-label=使用图像搜索', '@aria-label=Visual search', '@aria-label=Search using an image']:
                    try:
                        btn = self.page.ele(cam_sel, timeout=2)
                        if btn:
                            logger.info(f"{LogIndent.L2}📸 点击激活相机上传面板...")
                            btn.click(by_js=True)
                            time.sleep(1.5)
                            break
                    except Exception:
                        pass

                for sel in selectors:
                    try:
                        inp = self.page.ele(sel, timeout=2)
                        if inp:
                            file_input = inp
                            break
                    except Exception:
                        pass

            if not file_input:
                logger.warning(f"{LogIndent.L2}⚠️ 无法定位视觉搜索文件控件，跳过此任务")
                return False

            logger.info(f"{LogIndent.L2}📤 正在上传图片进行视觉搜索: {os.path.basename(img_path)}...")
            file_input.input(img_path)

            # 等待上传完成与搜索结果呈现（不要使用无参数的 wait.load_start，直接等待数秒让搜索请求完成）
            wait_sec = random.uniform(5, 7)
            logger.info(f"{LogIndent.L2}⏳ 等待视觉搜索结果呈现并同步状态 ({wait_sec:.1f} 秒)...")
            time.sleep(wait_sec)

            logger.success(f"{LogIndent.L2}✅ 账号{account_index} 必应视觉搜索已完成")
            return True

        except Exception as e:
            logger.error(f"{LogIndent.L2}❌ 视觉搜索任务异常: {e}")
            return False


