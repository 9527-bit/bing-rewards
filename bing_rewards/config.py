"""
常量、URL、OAuth 配置、正则表达式
"""

import re

# ===========================
# 脚本版本号
# ===========================
VERSION = "v1.0.1"  # 20260603

# ===========================
# URL 常量
# ===========================
REWARDS_URL = "https://rewards.bing.com/dashboard"
REWARDS_SIGNIN_URL = "https://rewards.bing.com/Signin/"
REWARDS_EARN_URL = "https://rewards.bing.com/earn"
BING_URL = "https://www.bing.com/"
SEARCH_HOME_WWW_URL = "https://www.bing.com/?form=ML2PCO"
SEARCH_HOME_CN_URL = "https://cn.bing.com/?form=ML2PCO"
SEARCH_REQUEST_URL = "https://cn.bing.com/search"

# ===========================
# Bing 账号设置 - 显示语言切换页
# ===========================
BING_ACCOUNT_GENERAL_URL = "https://www.bing.com/account/general"
BING_ACCOUNT_LANGUAGE_URL = (
    f"{BING_ACCOUNT_GENERAL_URL}"
    "?ru=https%3A%2F%2Fwww.bing.com%2Frewards"
    "&id=language_section#language-section"
)

# ===========================
# OAuth 令牌相关
# ===========================
OAUTH_CLIENT_ID = "0000000040170455"
OAUTH_REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"
OAUTH_SCOPE = "service::prod.rewardsplatform.microsoft.com::MBI_SSL"
OAUTH_AUTHORIZE_URL = (
    f"https://login.live.com/oauth20_authorize.srf"
    f"?client_id={OAUTH_CLIENT_ID}"
    f"&scope={OAUTH_SCOPE}"
    f"&response_type=code"
    f"&redirect_uri={OAUTH_REDIRECT_URI}"
)
OAUTH_TOKEN_URL = "https://login.live.com/oauth20_token.srf"

# ===========================
# Next.js Server Action ID 匹配正则
# ===========================
# 匹配特征："<hex_id>",x.callServer  其中 x 为任意变量名
RE_NEXT_ACTION = re.compile(r'"([0-9a-f]{32,})",[a-zA-Z_$][a-zA-Z0-9_$]*\.callServer')
