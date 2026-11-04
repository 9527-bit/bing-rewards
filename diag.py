import os
import sys
import time
import socket
import tempfile
import shutil
import subprocess

print("=" * 60)
print("🔍 Bing Rewards 浏览器底层启动诊断工具")
print("=" * 60)

# 1. 检测 Python 环境与操作系统
print(f"[1] 运行环境: Python {sys.version.split()[0]} on {sys.platform}")

# 2. 寻找浏览器路径
browser_path = None
try:
    from DrissionPage import ChromiumOptions
    from DrissionPage._base.chromium import Chromium
    cb = Chromium.__init__.__globals__['connect_browser']
    get_chrome_path = cb.__globals__['get_chrome_path']
    browser_path = get_chrome_path(None)
except Exception as e:
    print(f"DrissionPage 获取路径异常: {e}")

if not browser_path or not os.path.exists(browser_path):
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if os.path.exists(c):
            browser_path = c
            break

print(f"[2] 检测到的浏览器路径: {browser_path}")
if not browser_path or not os.path.exists(browser_path):
    print("❌ 错误：未找到 Chrome 或 Edge 浏览器安装路径！请确认已安装 Chrome。")
    sys.exit(1)

# 3. 检查 9222 端口占用情况
def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

port_9222_used = check_port("127.0.0.1", 9222)
print(f"[3] 端口 127.0.0.1:9222 当前占用状态: {'⚠️ 已被占用' if port_9222_used else '✅ 空闲'}")

# 4. 创建隔离的测试用户数据目录
test_dir = tempfile.mkdtemp(prefix="bing_diag_")
print(f"[4] 创建隔离测试配置目录: {test_dir}")

# 5. 测试原生启动 Chrome
test_port = 9222 if not port_9222_used else 9555
cmd = [
    browser_path,
    f"--remote-debugging-port={test_port}",
    f"--remote-debugging-address=127.0.0.1",
    f"--user-data-dir={test_dir}",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
]

# 如果是无头参数
if "--headless" in sys.argv:
    cmd.append("--headless=new")

print(f"[5] 启动原生进程测试 (端口: {test_port})...")
print(f"    命令: {' '.join(cmd[:4])} ...")

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
poll = proc.poll()

if poll is not None:
    print(f"❌ 浏览器启动后立即退出！退出代码 (Exit Code): {poll}")
    stdout, stderr = proc.communicate()
    print("--- STDOUT ---")
    print(stdout.decode('gbk', errors='ignore') or "(空)")
    print("--- STDERR ---")
    print(stderr.decode('gbk', errors='ignore') or "(空)")
else:
    print(f"✅ 浏览器进程正常存活！PID: {proc.pid}")
    # 测试连接端口
    import urllib.request
    import json
    try:
        url = f"http://127.0.0.1:{test_port}/json/version"
        req = urllib.request.Request(url, headers={"User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ 成功连接 127.0.0.1:{test_port} 调试接口！")
            print(f"    浏览器版本: {data.get('Browser')}")
            print(f"    CDP 地址: {data.get('webSocketDebuggerUrl')}")
    except Exception as e:
        print(f"❌ 无法通过 HTTP 连接 127.0.0.1:{test_port} : {e}")

    # 终止测试进程
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except:
        proc.kill()

shutil.rmtree(test_dir, ignore_errors=True)

# 6. 测试 DrissionPage 库直接调用
print(f"\n[6] 测试 DrissionPage 库初始化...")
try:
    from DrissionPage import ChromiumOptions, Chromium
    co = ChromiumOptions()
    if "--headless" in sys.argv:
        co.headless(True)
    else:
        co.headless(False)
    co.set_browser_path(browser_path)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--remote-debugging-address=127.0.0.1")
    browser = Chromium(co)
    print(f"🎉 DrissionPage 启动成功！当前标签页: {browser.latest_tab.title or browser.latest_tab.url}")
    browser.quit(timeout=2, force=True)
    print("✅ DrissionPage 测试完全通过！")
except Exception as e:
    print(f"❌ DrissionPage 启动报错: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
