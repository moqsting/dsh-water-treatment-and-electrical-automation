#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make-dspack.py —— 生成 profile 形态 .dspack（manifest v5 + pack-structure v3）。

契约（DSH-PackForge/DSH-PackForge specs/manifest/v5.md + pack-structure/v3.md）：
  ZIP 根：dspack.json（{"format":"dspack","version":3}）+ manifest.json（type=profile）
          + package.json + pnpm-workspace.yaml（机器文件，导入器据此重建依赖）
  overrides/ → $DSH_HOME/profiles/<profileName>/（工具链轻内容）
  home/      → $DSH_HOME/（技能 + AGENTS.md）
  pydeps 重内容走 manifest files[]（path+sha256+size+urls），不进 ZIP。

插件依赖（对照官方样例 desktop-pack 的做法：依赖用 npm 精确版本，不打 vendored）：
  - 工作台按钮插件（npm 未发布）→ git commit sha 坐标（唯一 git 依赖）
  - 4 个外来插件 + 官方 @dsh-packforge/dsh-pack-plugin（npm 已发布）→ npm 精确版本
  - koffi（native 传递依赖）→ pnpm-workspace.yaml 的 allowBuilds 放行 install 脚本

用法：py -3 setup\\make-dspack.py [--out <目录>]
"""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PACK_ROOT = SCRIPT_DIR.parent

NAME = "water-treatment-and-electrical-automation"
VERSION = "2.0.0"
PROFILE_NAME = "wet-automation"
DSH_VERSION = "0.2.0-rc.2"

# 工作台按钮插件（npm 未发布，git commit sha 坐标）
PLUGIN_REPO = "github:moqsting/dsh-engineering-workbench"
PLUGIN_SHA = "eb6d850cdbd6712abadc48a6a05b22f894fee9ee"
PLUGIN_NAME = "dsh-engineering-workbench"

# 招标工作台插件（npm 0.6.1 未发布，git commit sha 坐标；prepare 构建 lib/）
TENDER_REPO = "github:moqsting/dsh-tender-workbench"
TENDER_SHA = "21a6a85e043f4c8d67ad0f0d394f8737e3eb6989"
TENDER_NAME = "dsh-tender-workbench"

# npm registry 已发布的插件（精确版本）
NPM_PLUGINS = {
    "@michengai/dsh-skills-manager": "1.1.8",
    "@michengai/dsh-automation": "0.1.53",
    "dshmarket": "1.66.8",
    "dsh-bottom-info-bar": "1.20.13",
    "dsh-mcp-connector": "0.2.66",        # 企查查 MCP 连接器（提供工具，必须先于 tender-workbench）
    "dsh-better-sidebar": "0.24.1",       # 可视化工作台 Tab 容器
    "@dsh-packforge/dsh-pack-plugin": "0.3.5",   # 官方规范导入器（整合包必备）
}

PYDEP_TARBALL = "pydeps-2.0.0.tar.gz"
PYDEP_URL = ("https://github.com/moqsting/dsh-water-treatment-and-electrical-automation/"
             f"releases/download/v{VERSION}/{PYDEP_TARBALL}")

DISPLAY_NAME = {
    "zh-CN": "水处理与电气自动化整合包",
    "en-US": "Water Treatment & Electrical Automation Pack",
}
DESCRIPTION = {
    "zh-CN": "水处理与电气自动化工程师 DSH 整合包：PLC 编程辅助、投标报价清单、招标与价格查询、"
             "CAD 识图、工艺/电气计算、规范查询、本地工作台（侧边栏一键启停）",
    "en-US": "Integration pack for water-treatment and electrical-automation engineers: "
             "PLC programming, bid/quotation sheets, tender & price query, CAD reading, "
             "process/electrical calcs, standards lookup, local workbench.",
}
AUTHOR = "moqsting"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bundles_list() -> list:
    # 挂载顺序：提供方先于消费方（dsh-mcp-connector 必须在 dsh-tender-workbench 之前）
    return [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-web-app",
        PLUGIN_NAME,                       # 工作台按钮（git）
        "@michengai/dsh-skills-manager",
        "@michengai/dsh-automation",
        "dshmarket",
        "dsh-bottom-info-bar",
        "dsh-mcp-connector",               # 提供 mcp__qcc-tender__* 工具
        "dsh-better-sidebar",
        TENDER_NAME,                       # 招标工作台（消费工具，git）
        "@dsh-packforge/dsh-pack-plugin",  # 官方导入器最后
    ]


def dependencies_map() -> dict:
    return {PLUGIN_REPO: PLUGIN_SHA, TENDER_REPO: TENDER_SHA, **NPM_PLUGINS}


def build_manifest() -> dict:
    tar = PACK_ROOT / "release" / PYDEP_TARBALL
    if not tar.is_file():
        raise SystemExit(f"缺少 {tar}——请先运行 setup/pack-pydeps.py 生成 pydeps 包")
    files = [{
        "path": f"pydeps/{PYDEP_TARBALL}",
        "sha256": sha256_of(tar),
        "size": tar.stat().st_size,
        "urls": [PYDEP_URL],
    }]
    return {
        "manifestVersion": 5,
        "type": "profile",
        "name": NAME,
        "version": VERSION,
        "displayName": DISPLAY_NAME,
        "description": DESCRIPTION,
        "author": AUTHOR,
        "dshVersion": DSH_VERSION,
        "profileName": PROFILE_NAME,
        "bundles": bundles_list(),
        "dependencies": dependencies_map(),
        "files": files,
    }


def build_machine_package() -> dict:
    """profile 机器文件快照（ZIP 根 package.json；导入器会按 manifest 权威重建）。"""
    deps = {
        PLUGIN_NAME: f"{PLUGIN_REPO}#{PLUGIN_SHA}",
        TENDER_NAME: f"{TENDER_REPO}#{TENDER_SHA}",
        **NPM_PLUGINS,
    }
    return {
        "name": f"dsh-profile-{PROFILE_NAME}",
        "private": True,
        "dependencies": deps,
        "dsh": {
            "profile": {
                "bundles": bundles_list(),
            }
        },
    }


def build_workspace() -> str:
    """pnpm-workspace.yaml 机器文件（YAML 文本）。

    allowBuilds 放行 dsh-tender-workbench 的 prepare 构建（git 源码形态需要现场构建 lib/；
    npm 发行版无需此键）。键为精确坐标，跟随 commit sha。
    """
    lines = [
        "packages:",
        "  - .",
        "nodeLinker: hoisted",
        "autoInstallPeers: false",
        "allowBuilds:",
        f'  "dsh-tender-workbench@https://codeload.github.com/moqsting/dsh-tender-workbench/tar.gz/{TENDER_SHA}": true',
    ]
    return "\n".join(lines) + "\n"


SKIP_DIRS = {"__pycache__", ".git", "node_modules", "vendor", "reports", "pydeps", "release", "dist"}
SKIP_FILES = {"ui-workspace.json", "cad_env.json", ".gitkeep"}


def pack_toolchain(z: zipfile.ZipFile, label: str, src_base: Path, arc_base: str, dirs: tuple):
    for d in dirs:
        base = src_base / d
        if not base.is_dir():
            continue
        for root, dirnames, files in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
            for f in files:
                if f in SKIP_FILES:
                    continue
                p = Path(root) / f
                z.write(p, f"{arc_base}/{p.relative_to(src_base).as_posix()}")
    print(f"  {label}: 已打包 {dirs}")


def self_check(m: dict, zip_path: Path) -> tuple:
    lines = []
    ok = True

    def chk(cond, text):
        nonlocal ok
        ok = ok and cond
        lines.append(("PASS  " if cond else "FAIL  ") + text)

    chk(m["manifestVersion"] == 5, "manifestVersion == 5")
    chk(m["type"] == "profile", "type == profile")
    chk(bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", m["name"])), "name 为 kebab-case")
    chk(bool(re.match(r"^\d+\.\d+\.\d+$", m["version"])), "version 为 semver")
    chk(PLUGIN_NAME in m["bundles"] and TENDER_NAME in m["bundles"] and "@dsh-packforge/dsh-pack-plugin" in m["bundles"],
        "bundles 含工作台 + 招标工作台 + 官方 dsh-pack-plugin")
    # 挂载顺序：dsh-mcp-connector 必须在 dsh-tender-workbench 之前（提供方先于消费方）
    bi = m["bundles"].index("dsh-mcp-connector") if "dsh-mcp-connector" in m["bundles"] else -1
    bt = m["bundles"].index(TENDER_NAME) if TENDER_NAME in m["bundles"] else -1
    chk(0 <= bi < bt, "bundles 顺序：dsh-mcp-connector 先于 dsh-tender-workbench")
    # 依赖：2 个 git 坐标 40 位 sha（工作台 + 招标）+ npm 精确版本
    for coord in (PLUGIN_REPO, TENDER_REPO):
        dep = m["dependencies"].get(coord)
        chk(bool(re.match(r"^[0-9a-f]{40}$", dep or "")), f"dependencies 的 {coord} 为 40 位 commit sha")
    chk(all(re.match(r"^\d+\.\d+\.\d+$", m["dependencies"].get(k, "")) for k in NPM_PLUGINS),
        "dependencies 的 npm 插件为精确版本")
    chk("vendored" not in m, "无 vendored（npm 精确版本；2 个 git 依赖由 allowBuilds 放行构建）")
    chk(len(m["files"]) >= 1, "files[] 非空（pydeps 重内容）")
    if m["files"]:
        e = m["files"][0]
        chk(bool(re.match(r"^pydeps/[^/]+$", e["path"])), "files[0].path 落在 pydeps/ 内")
        chk(bool(re.match(r"^[0-9a-f]{64}$", e["sha256"])), "files[0].sha256 为 64 位 hex")
        chk(isinstance(e["size"], int) and e["size"] > 0, "files[0].size 为正整数")
        chk(all(u.startswith("https://") for u in e["urls"]), "files[0].urls 为 https 地址")

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        inner = [n for n in names if "/" in n]
        chk("dspack.json" in names and "manifest.json" in names, "ZIP 根含 dspack.json + manifest.json")
        chk("package.json" in names and "pnpm-workspace.yaml" in names,
            "ZIP 根含机器文件 package.json + pnpm-workspace.yaml")
        chk(all(n.startswith("overrides/") or n.startswith("home/") for n in inner),
            "用户文件均在 overrides/ 或 home/ 内")
        chk("overrides/wta/ui/server.py" in names, "overrides/wta/ui/server.py 存在（工作台）")
        chk("home/AGENTS.md" in names, "home/AGENTS.md 存在（全局指令）")
        skills = [n for n in names if n.startswith("home/skills/") and n.endswith("SKILL.md")]
        chk(len(skills) == 11, f"home/skills 含 11 个技能（实际 {len(skills)}）")
        chk(not any("node_modules" in n for n in names), "不含 node_modules（依赖由导入器重建）")
        chk(not any("pydeps/" in n for n in names), "不含 pydeps（走 files[] 指针）")
        chk(not any(n.startswith("home/.credentials") or n.startswith("home/settings.yaml") for n in names),
            "不含凭据与全局设置（安全过滤）")
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PACK_ROOT / "release"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest()
    dspack = out_dir / f"{NAME}-{VERSION}.dspack"

    with zipfile.ZipFile(dspack, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dspack.json", '{"format":"dspack","version":3}')
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        z.writestr("package.json", json.dumps(build_machine_package(), ensure_ascii=False, indent=2) + "\n")
        z.writestr("pnpm-workspace.yaml", build_workspace())
        # overrides/wta/ → profile 根（工具链轻内容）
        pack_toolchain(z, "overrides/wta",
                       PACK_ROOT, "overrides/wta",
                       ("ui", "scripts", "templates", "data", "config", "docs"))
        # home/ → $DSH_HOME（技能 + AGENTS.md）
        skills = PACK_ROOT / "skills"
        if skills.is_dir():
            for d in sorted(skills.iterdir()):
                sk = d / "SKILL.md"
                if sk.is_file():
                    z.write(sk, f"home/skills/{d.name}/SKILL.md")
            print("  home/skills: 已打包")
        agents = PACK_ROOT / "AGENTS.md"
        if agents.is_file():
            z.write(agents, "home/AGENTS.md")
            print("  home/AGENTS.md: 已打包")

    ok, lines = self_check(manifest, dspack)
    for line in lines:
        print(line)
    print(f"输出: {dspack}  ({dspack.stat().st_size} 字节)")
    if not ok:
        print("自检未通过")
        sys.exit(1)
    print("自检全部通过")


if __name__ == "__main__":
    main()
