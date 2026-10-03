# -*- coding: utf-8 -*-
"""start.pyw —— 工作台启动器（pythonw 运行，无控制台窗口）

用法：pythonw.exe start.pyw（桌面快捷方式即此命令）
行为：
  1. 若工作台已在运行 → 直接打开浏览器；
  2. 否则后台启动 ui/server.py（无窗口，日志写 reports/ui/server.log）→ 打开浏览器。
停止：工作台"设置"页 → "停止服务"（或任务管理器结束 python.exe）。
"""
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

UI_ROOT = Path(__file__).resolve().parent
LOG = UI_ROOT.parent / "reports" / "ui" / "server.log"
PORT_RANGE = range(8618, 8628)
WAIT_SECONDS = 15


def find_running():
    for port in PORT_RANGE:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ) as r:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("name") == "integration-pack-workbench":
                    return port
        except Exception:  # noqa: BLE001
            continue
    return None


def main():
    running = find_running()
    if running:
        webbrowser.open(f"http://127.0.0.1:{running}")
        return

    LOG.parent.mkdir(parents=True, exist_ok=True)
    logf = open(LOG, "ab", buffering=0)  # noqa: SIM115
    # 关键：用 sys.executable（pythonw.exe 下即 pythonw，无控制台）启动，
    # 不能用 py 启动器——py.exe 在无控制台时会给子进程新建一个控制台窗口。
    subprocess.Popen(
        [sys.executable, str(UI_ROOT / "server.py")],
        cwd=str(UI_ROOT),
        stdout=logf,
        stderr=logf,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )

    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        running = find_running()
        if running:
            webbrowser.open(f"http://127.0.0.1:{running}")
            return
        time.sleep(0.5)
    webbrowser.open("http://127.0.0.1:8618")


if __name__ == "__main__":
    main()
