"""
Bing Rewards 自动化执行入口
默认完全按照系统环境启动浏览器（支持窗口界面模式，也支持 --headless 无头模式）
"""

import os
import sys
from pathlib import Path

# 确保切换到脚本所在目录，并加到模块搜索路径
ROOT_DIR = Path(__file__).resolve().parent
os.chdir(ROOT_DIR)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bing_rewards.main import main

if __name__ == "__main__":
    main()
