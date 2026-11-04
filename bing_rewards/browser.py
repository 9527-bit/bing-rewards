"""
BingRewardsBrowser：组合全部功能 Mixin 的主浏览器类

各能力拆分到独立 Mixin：
  - BrowserCoreMixin  浏览器/虚拟显示器初始化、Cookie 管理、辅助方法、资源清理
  - AuthMixin         Microsoft 登录（密码登录、Cookie 登录、登录验证）
  - PointsMixin       从 /earn 页面解析积分、连胜、活动卡片
  - SearchTasksMixin  搜索任务
  - ReadTasksMixin    OAuth 令牌、APP 阅读、APP 签到
  - ActivityTasksMixin Dashboard 卡片、积分领取、Earn 页面任务、语言切换
"""

from .browser_core import BrowserCoreMixin
from .auth import AuthMixin
from .points import PointsMixin
from .tasks_search import SearchTasksMixin
from .tasks_read import ReadTasksMixin
from .tasks_activity import ActivityTasksMixin


class BingRewardsBrowser(
    BrowserCoreMixin,
    AuthMixin,
    PointsMixin,
    SearchTasksMixin,
    ReadTasksMixin,
    ActivityTasksMixin,
):
    """Bing Rewards 自动化主类：整合浏览器控制、登录、积分、搜索、阅读与活动任务。

    __init__（浏览器与虚拟显示器初始化）由 BrowserCoreMixin 提供，无需在此重复定义。
    """
    pass
