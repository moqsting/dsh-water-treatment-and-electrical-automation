# -*- coding: utf-8 -*-
r"""setup/deploy-to-instance.py —— 把整合包部署到本地 DSH 实例并（可选）启动

用法：
  py -3 setup\deploy-to-instance.py                  # 仅导入（技能 + AGENTS + 插件 + pnpm 链接）
  py -3 setup\deploy-to-instance.py --start          # 导入后启动 web 实例并打印 token URL
  py -3 setup\deploy-to-instance.py --profile X --port 8787 --start

行为：
  1. 复制 skills/<name>/SKILL.md → $DSH_HOME/skills/<name>/SKILL.md
  2. 复制 AGENTS.md → $DSH_HOME/AGENTS.md（全局指令）
  3. 复制 plugins/open-workbench → $DSH_HOME/profiles/<profile>/open-workbench/
  4. 更新该 profile 的 package.json（bundles + dependencies 挂插件）
  5. pnpm install（链接本地插件）
  6. （--start）用 DSH 版本目录启动 web，解析并打印 token URL
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent
PLUGIN = PACK / "plugins" / "open-workbench"
DEFAULT_DSH_HOME = Path.home() / ".dsh"
DEFAULT_DSH_VERSION_DIR = Path.home() / ".dsh-win" / "versions" / "0.2.0-rc.2_test"


def sh(profile_dir, *args):
    return subprocess.run(list(args), cwd=str(profile_dir), capture_output=True, text=True)


def import_pack(dsh_home, profile):
    home = Path(dsh_home)
    # 1) 技能
    n = 0
    for src in (PACK / "skills").glob("*/SKILL.md"):
        dst = home / "skills" / src.parent.name / "SKILL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    # 2) AGENTS.md
    if (PACK / "AGENTS.md").is_file():
        shutil.copy2(PACK / "AGENTS.md", home / "AGENTS.md")
    # 3) 插件
    dst_plugin = home / "profiles" / profile / "open-workbench"
    shutil.rmtree(dst_plugin, ignore_errors=True)
    shutil.copytree(PLUGIN, dst_plugin)
    # 4) package.json 挂插件
    pkg_path = home / "profiles" / profile / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    pkg.setdefault("dependencies", {})["dsh-open-workbench"] = "file:open-workbench"
    bundles = pkg["dsh"]["profile"]["bundles"]
    if "dsh-open-workbench" not in bundles:
        bundles.append("dsh-open-workbench")
    pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 5) pnpm install
    r = sh(home / "profiles" / profile, "pnpm", "install")
    print(f"  技能 {n} 个 + AGENTS + 插件已部署到 {home}")
    print("  pnpm install 退出码", r.returncode)
    return home, profile


def start_instance(dsh_home, profile, port, version_dir):
    home = Path(dsh_home)
    vdir = Path(version_dir)
    env = dict(os.environ)
    env["DSH_HOME"] = str(home)
    cmd = [str(vdir / "dsh.cmd"), "--profile", profile, "--port", str(port), "--host", "127.0.0.1", "--no-open"]
    proc = subprocess.Popen(cmd, cwd=str(vdir), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # 读 stdout 拿 token URL
    token = None
    deadline = time.time() + 60
    line_buf = ""
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line:
            line_buf += line
            m = re.search(r"http://127\.0\.0\.1:\d+/\?token=([^\s]+)", line_buf)
            if m:
                token = m.group(0)
                break
        elif proc.poll() is not None:
            break
    if token:
        print(f"\nDSH 实例已启动：{token}")
        print("（该进程在后台持续运行；停止：结束 dsh 进程或 Ctrl+C 无法用于后台，请用任务管理器结束）")
    else:
        print("\n未能捕获启动 URL，stdout 最后输出：")
        print(line_buf[-2000:])
    return token


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsh-home", default=str(DEFAULT_DSH_HOME))
    ap.add_argument("--profile", default="0.2.0-rc.2_test")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--version-dir", default=str(DEFAULT_DSH_VERSION_DIR))
    ap.add_argument("--start", action="store_true")
    args = ap.parse_args()

    import_pack(args.dsh_home, args.profile)
    if args.start:
        start_instance(args.dsh_home, args.profile, args.port, args.version_dir)


if __name__ == "__main__":
    main()
