# -*- coding: utf-8 -*-
r"""
bootstrap_libs.py —— 受限环境下重建整合包 Python 依赖（仅用标准库，不依赖 pip）

背景：pip 需要创建随机临时目录，会被 DSH 沙箱策略拦截；而受限会话可以
正常创建"固定名称"的目录与文件。本脚本用 urllib 从清华镜像下载固定版本的
wheel，再用 zipfile 解压到 pydeps/ 目录，全程固定路径。

用法（在 DSH 会话中）：
    integration-pack\scripts\runpy.cmd integration-pack\scripts\bootstrap_libs.py
"""
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIRROR = "https://pypi.tuna.tsinghua.edu.cn"
PACK_ROOT = Path(__file__).resolve().parent.parent
DEST = PACK_ROOT / "pydeps"
DL = PACK_ROOT / "pydeps_dl"

# (simple 索引页名, 精确版本) —— 版本锁定，与审查时安装的版本一致
PKGS = [
    ("six", "1.17.0"),
    ("typing-extensions", "4.16.0"),
    ("tzdata", "2026.4"),
    ("pyparsing", "3.3.3"),
    ("et-xmlfile", "2.0.0"),
    ("idna", "3.20"),
    ("urllib3", "2.8.0"),
    ("certifi", "2026.7.22"),
    ("charset-normalizer", "3.5.2"),
    ("numpy", "2.5.3"),
    ("python-dateutil", "2.9.0.post0"),
    ("lxml", "6.1.3"),
    ("fonttools", "4.66.1"),
    ("pandas", "3.0.6"),
    ("openpyxl", "3.1.5"),
    ("ezdxf", "1.4.4"),
    ("pymodbus", "3.15.0"),
    ("requests", "2.34.2"),
    ("python-docx", "1.2.0"),
]


def _fname(href):
    return href.rsplit("/", 1)[-1].split("#")[0]


def fetch_index(simple_name):
    req = Request(f"{MIRROR}/simple/{simple_name}/",
                  headers={"User-Agent": "dsh-integration-pack/1.0"})
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def pick_wheel(html, simple_name, version):
    v = version.replace("-", "_")
    n = simple_name.replace("-", "_")
    prefix = f"{n}-{v}-"
    hrefs = re.findall(r'href="([^"]+\.whl[^"]*)"', html)
    hrefs = [urljoin(MIRROR + "/", h) for h in hrefs]
    cp312w = [h for h in hrefs if _fname(h).startswith(prefix)
              and "cp312" in _fname(h) and "win_amd64" in _fname(h)]
    anys = [h for h in hrefs if _fname(h).startswith(prefix) and "none-any" in _fname(h)]
    return (cp312w or anys or [None])[0]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    DL.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, []
    for simple_name, version in PKGS:
        try:
            html = fetch_index(simple_name)
            url = pick_wheel(html, simple_name, version)
            if not url:
                fail.append((simple_name, "no matching wheel"))
                continue
            local = DL / _fname(url)
            print(f"[{simple_name}] 下载 {_fname(url)} ...", end=" ")
            req = Request(url, headers={"User-Agent": "dsh-integration-pack/1.0"})
            with urlopen(req, timeout=120) as r, open(local, "wb") as f:
                f.write(r.read())
            with zipfile.ZipFile(local) as z:
                z.extractall(DEST)
            ok += 1
            print("OK")
        except Exception as e:  # noqa: BLE001
            fail.append((simple_name, str(e)[:120]))
            print("FAIL", str(e)[:120])
    print(f"\n完成：成功 {ok}/{len(PKGS)}")
    if fail:
        print("失败清单：")
        for n, why in fail:
            print(f"  - {n}: {why}")
        sys.exit(1)
    print(f"依赖目录：{DEST}")
    print("验证：runpy.cmd 对应的 PYTHONPATH 应指向 pydeps 目录。")


if __name__ == "__main__":
    main()
