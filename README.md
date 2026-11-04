# Bing Rewards Automation

全自动化的 Microsoft Rewards (Bing Rewards) 积分任务执行脚本。基于 [DrissionPage](https://github.com/g1879/DrissionPage) 驱动，支持有界面（GUI）与无头（Headless）双模式自适应，支持多账号轮询与本地 Cookie 持久化。

## ✨ 特性

- 🚀 **智能浏览器驱动**：基于 DrissionPage，免 webdriver，支持 Chrome 与 Edge。
- 🛡️ **反检测与防锁死**：独立 `browser_profile` 存储机制，完全隔离系统默认 Chrome 进程与临时目录冲突。
- 🔄 **自动自愈降级**：优先以桌面窗口模式运行，若处于 Windows Server、锁屏或计划任务（ZTasker）无交互式桌面环境，自动平滑切换至 Headless 无头模式。
- 👥 **多账号与本地凭证**：
  - 支持多账号轮询切换；
  - 登录成功后自动将最新 Cookie 持久化至本地，后续直接免密免验证注入登录；
  - 自动拒绝 Passkey / Windows Hello 弹窗中断。
- 🔍 **全方位任务覆盖**：
  - PC 端 / 移动端桌面端搜索点数；
  - 每日热点资讯热搜词动态拉取（内置多重公共 API 与本地兜底词库）；
  - 必应视觉搜索（Visual Search）图片上传任务；
  - 新闻阅读与日常任务打卡。
- 🛠️ **配套诊断工具**：内置 `diag.py`，秒级排查浏览器路径、端口连通性及 CDP 接口状态。

---

## 📦 快速开始

### 1. 安装依赖

推荐 Python 3.9 ~ 3.13 环境：

```bash
pip install -r requirements.txt
```

### 2. 配置账号

复制配置模板：
```bash
cp bing_accounts.example.json bing_accounts.json
```

编辑 `bing_accounts.json`，填入你的微软账号与密码：
```json
[
  {
    "username": "your_account@outlook.com",
    "password": "your_password"
  }
]
```

> **注意**：`bing_accounts.json` 和生成的 `bing_cookies.json` 已被加入 `.gitignore`，不会被上传。

### 3. 可选：配置代理（可选环境变量）

若需使用品赞等第三方代理，可在系统环境中设置：
```bash
export PINZAN_API_URL="你的品赞提取链接"
```

---

## 🚀 运行方式

### 运行完整自动化任务
```bash
python run.py
```

### 指定无头模式运行（适合云服务器 / 后台挂机）
```bash
python run.py --headless
```

### 调试单个账号登录
```bash
# 调试账号 1（使用本地 Cookie 优先）
python -m bing_rewards.debug_login 1

# 调试账号 1（强制纯密码重新登录并刷新 Cookie）
python -m bing_rewards.debug_login 1 --no-cookie
```

### 浏览器底层启动诊断
遇到启动失败或环境异常时，运行以下命令秒级排查：
```bash
python diag.py
```

---

## ⚠️ 免责声明

本项目仅供 Python 自动化技术交流与学习使用，请勿用于非法用途或恶意刷取积分。

