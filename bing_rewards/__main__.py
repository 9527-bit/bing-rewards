"""
包入口：支持 `python -m bing_rewards` 运行。

原单文件 bing.py 仍保留（作为备份/参考），其青龙 cron 头如下：
  cron: 10 0,8,16 * * *
  new Env("Bing Rewards 自动化(密码登录版)")
"""

from .main import main

if __name__ == "__main__":
    main()
