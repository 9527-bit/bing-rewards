"""
热搜词管理器：从多个公开免费 API 获取今日热点作为搜索词
"""

import random
import requests

from .log import logger, LogIcon, LogTag

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
