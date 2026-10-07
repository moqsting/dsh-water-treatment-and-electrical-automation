#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make-dspack.py —— 生成 profile 形态 .dspack（manifest v5 + pack-structure v3）。

契约（DSH-PackForge/DSH-PackForge specs/manifest/v5.md + pack-structure/v3.md）：
  ZIP 根：dspack.json（{"format":"dspack","version":3}）+ manifest.json（type=profile）
          + package.json + pnpm-workspace.yaml（机器文件，导入器据此重建依赖）
  overrides/ → $DSH_HOME/profiles/<profileName>/（工具链轻内容）
  home/      → $DSH_HOME/（技能 + AGENTS.md）
  pydeps 重内容走 manifest files[]（path+sha256+size+urls），不进 ZIP。

插件依赖（离线可导入：7 个 git 插件 + 7 个 npm 插件全部 vendored）：
  - 全部依赖的 npm 包 tarball 放 ZIP 根 vendor/ 下，并在 manifest vendored{} 声明
    （manifest v5 §12：version/sha256/size/path[/reason]；path 必须在 vendor/ 下且 .tgz，
     且 vendor/ 内每个文件都必须登记）。导入端把 tarball 落到 vendor-blobs/ 并把依赖 spec
     改写成 file:vendor-blobs/...，全程零网络——无 VPN 机器也能完整导入。
  - git 坐标的 vendored[].version 必须等于 dependencies 里钉死的那个 commit sha（规范硬约束）。
  - koffi（native 传递依赖）→ pnpm-workspace.yaml 的 allowBuilds 放行 install 脚本

用法：py -3 setup\\make-dspack.py [--out <目录>]
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PACK_ROOT = SCRIPT_DIR.parent

NAME = "water-treatment-and-electrical-automation"
VERSION = "2.3.7"
PROFILE_NAME = "wet-automation"
DSH_VERSION = "0.2.0-rc.2"

# 工作台插件（npm 未发布，git commit sha 坐标）
PLUGIN_REPO = "github:moqsting/dsh-engineering-workbench"
PLUGIN_SHA = "1c6a23470af49bbcef9789efa250aa47d632143f"
PLUGIN_NAME = "dsh-engineering-workbench"

# 招标工作台插件（npm 0.6.1 未发布，git commit sha 坐标；prepare 构建 lib/）
TENDER_REPO = "github:moqsting/dsh-tender-workbench"
TENDER_SHA = "21a6a85e043f4c8d67ad0f0d394f8737e3eb6989"
TENDER_NAME = "dsh-tender-workbench"

# 5 个新增插件（fork 修复后 git commit sha 坐标，见各自 MODIFICATIONS.md）
CALC_REPO = "github:moqsting/dsh-tool-calculator"
CALC_SHA = "3a089c12714f18d5c6b3044d23945368d0bcb518"
CALC_NAME = "dsh-tool-calculator"
CAD_REPO = "github:moqsting/dsh-cad"
CAD_SHA = "602cef5c0a61b340f395397a5342c1860c2ab1c4"
CAD_NAME = "dsh-cad"
WPS_REPO = "github:moqsting/dsh-plugin-wps-office-next"
WPS_SHA = "85fd9df2762f23d7e93af171cc0bd9bcadf1bdb7"
WPS_NAME = "dsh-plugin-wps-office-next"
OFFICE_REPO = "github:moqsting/dsh-office-toolkit"
OFFICE_SHA = "81454e1f8e96a5b48a2462c794b2348fb3570d50"
OFFICE_NAME = "dsh-office-toolkit"
ELECTRO_REPO = "github:moqsting/dsh-electro-lab"
ELECTRO_SHA = "4b34aa56387e36abce518832144a9a3ba1f9d7f8"
ELECTRO_NAME = "dsh-electro-lab"

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

PYDEP_TARBALL = "pydeps-2.3.7.tar.gz"
PYDEP_URL = ("https://github.com/moqsting/dsh-water-treatment-and-electrical-automation/"
             f"releases/download/v{VERSION}/{PYDEP_TARBALL}")

# 下载源顺序（导入器逐个尝试，成功即止）：镜像在前（国内可直连、快），GitHub 原生在后做权威回退。
# 同一加速服务的两个域名互为备份；所有源共用 manifest 里的 sha256 校验，镜像即使投毒也会被拒。
PYDEP_MIRRORS = [
    f"https://gh-proxy.com/{PYDEP_URL}",
    f"https://cdn.gh-proxy.com/{PYDEP_URL}",
]
PYDEP_URLS = [*PYDEP_MIRRORS, PYDEP_URL]

DISPLAY_NAME = {
    "zh-CN": "水处理与电气自动化整合包",
    "en-US": "Water Treatment & Electrical Automation Pack",
}
DESCRIPTION = {
    "zh-CN": "水处理与电气自动化工程师 DSH 整合包：PLC 编程辅助、投标报价清单、招标与价格查询、"
             "CAD 识图、工艺/电气计算、规范查询、本地工作台（DSH 原生面板）",
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
        PLUGIN_NAME,                       # 工作台（DSH 原生主面板，git）
        "@michengai/dsh-skills-manager",
        "@michengai/dsh-automation",
        "dshmarket",
        "dsh-bottom-info-bar",
        "dsh-mcp-connector",               # 提供 mcp__qcc-tender__* 工具
        "dsh-better-sidebar",
        TENDER_NAME,                       # 招标工作台（消费工具，git）
        CALC_NAME,                          # 计算器（fork，git）
        OFFICE_NAME,                        # Office 读写（fork，git）
        WPS_NAME,                           # WPS 办公（fork，git，条件启用）
        CAD_NAME,                           # CAD 可视化（fork，git）
        ELECTRO_NAME,                       # 电气计算（fork，git）
        "@dsh-packforge/dsh-pack-plugin",  # 官方导入器最后
    ]


def dependencies_map() -> dict:
    return {
        PLUGIN_REPO: PLUGIN_SHA, TENDER_REPO: TENDER_SHA,
        CALC_REPO: CALC_SHA, CAD_REPO: CAD_SHA, WPS_REPO: WPS_SHA,
        OFFICE_REPO: OFFICE_SHA, ELECTRO_REPO: ELECTRO_SHA,
        **NPM_PLUGINS,
    }


VENDOR_DIR = PACK_ROOT / "release" / "vendor"


def coord_pkg_name(coord: str) -> str:
    """依赖坐标 → npm 包名（git 坐标取仓库名，npm 坐标原样）。"""
    return coord.rsplit("/", 1)[-1] if coord.startswith("github:") else coord


def vendor_tgz_identity(path: Path):
    """读 tarball 内 package/package.json 的 (name, version)。"""
    with tarfile.open(path, "r:gz") as tf:
        member = next((m for m in tf.getmembers() if m.name.endswith("package/package.json")), None)
        if member is None:
            raise SystemExit(f"{path.name} 内找不到 package/package.json")
        fh = tf.extractfile(member)
        pkg = json.loads(fh.read().decode("utf-8"))
    return pkg.get("name", ""), pkg.get("version", "")


def vendored_map() -> dict:
    """按 release/vendor/*.tgz 生成 manifest v5 §12 的 vendored{}（坐标 → 五字段）。

    version 必须与 dependencies 钉死的值一致：git 坐标是那个 40 位 commit sha，
    npm 坐标是精确版本。规范校验不通过会导致整包"拒装"。
    """
    if not VENDOR_DIR.is_dir():
        raise SystemExit(f"缺少 {VENDOR_DIR}——请先用 npm pack 准备各依赖的 .tgz")
    by_name = {}
    for f in sorted(VENDOR_DIR.glob("*.tgz")):
        name, _ver = vendor_tgz_identity(f)
        if not name:
            raise SystemExit(f"{f.name} 的 package.json 缺 name")
        by_name[name] = f
    out = {}
    for coord, version in dependencies_map().items():
        nm = coord_pkg_name(coord)
        f = by_name.get(nm)
        if f is None:
            raise SystemExit(f"vendor/ 缺依赖 {coord}（期望包名 {nm}）")
        out[coord] = {
            "version": version,
            "sha256": sha256_of(f),
            "size": f.stat().st_size,
            "path": f"vendor/{f.name}",
            "reason": "local-modified" if coord.startswith("github:") else "explicit",
        }
    return out


def build_manifest() -> dict:
    tar = PACK_ROOT / "release" / PYDEP_TARBALL
    if not tar.is_file():
        raise SystemExit(f"缺少 {tar}——请先运行 setup/pack-pydeps.py 生成 pydeps 包")
    files = [{
        "path": f"pydeps/{PYDEP_TARBALL}",
        "sha256": sha256_of(tar),
        "size": tar.stat().st_size,
        "urls": list(PYDEP_URLS),
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
        "vendored": vendored_map(),
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
    new_names = (CALC_NAME, CAD_NAME, WPS_NAME, OFFICE_NAME, ELECTRO_NAME)
    chk(PLUGIN_NAME in m["bundles"] and TENDER_NAME in m["bundles"]
        and all(n in m["bundles"] for n in new_names)
        and "@dsh-packforge/dsh-pack-plugin" in m["bundles"],
        "bundles 含工作台 + 招标 + 5 个新插件 + 官方 dsh-pack-plugin")
    # 5 个新插件位于 dsh-web-app 之后、官方导入器之前（靠后挂载）
    web_idx = m["bundles"].index("@deepseek-ai/dsh-web-app") if "@deepseek-ai/dsh-web-app" in m["bundles"] else -1
    pack_idx = m["bundles"].index("@dsh-packforge/dsh-pack-plugin") if "@dsh-packforge/dsh-pack-plugin" in m["bundles"] else -1
    new_idx = [m["bundles"].index(n) for n in new_names if n in m["bundles"]]
    chk(bool(new_idx) and web_idx >= 0 and pack_idx >= 0 and all(web_idx < i < pack_idx for i in new_idx),
        "bundles 顺序：5 个新插件位于 dsh-web-app 之后、dsh-pack-plugin 之前")
    # 挂载顺序：dsh-mcp-connector 必须在 dsh-tender-workbench 之前（提供方先于消费方）
    bi = m["bundles"].index("dsh-mcp-connector") if "dsh-mcp-connector" in m["bundles"] else -1
    bt = m["bundles"].index(TENDER_NAME) if TENDER_NAME in m["bundles"] else -1
    chk(0 <= bi < bt, "bundles 顺序：dsh-mcp-connector 先于 dsh-tender-workbench")
    # 依赖：7 个 git 坐标 40 位 sha（工作台 + 招标 + 5 个新插件）+ npm 精确版本
    for coord in (PLUGIN_REPO, TENDER_REPO, CALC_REPO, CAD_REPO, WPS_REPO, OFFICE_REPO, ELECTRO_REPO):
        dep = m["dependencies"].get(coord)
        chk(bool(re.match(r"^[0-9a-f]{40}$", dep or "")), f"dependencies 的 {coord} 为 40 位 commit sha")
    chk(all(re.match(r"^\d+\.\d+\.\d+$", m["dependencies"].get(k, "")) for k in NPM_PLUGINS),
        "dependencies 的 npm 插件为精确版本")
    vm = m.get("vendored")
    _ndeps = len(m["dependencies"])
    chk(isinstance(vm, dict) and len(vm) == _ndeps,
        f"vendored 覆盖全部 {_ndeps} 个依赖（实际 {len(vm) if isinstance(vm, dict) else '无'}）")
    _bad = []
    for _coord, _e in (vm or {}).items():
        if not re.match(r"^vendor/[^/]+\.tgz$", str(_e.get("path", ""))):
            _bad.append(f"{_coord}.path")
        if _e.get("version") != m["dependencies"].get(_coord):
            _bad.append(f"{_coord}.version")
        if not re.match(r"^[0-9a-f]{64}$", str(_e.get("sha256", ""))):
            _bad.append(f"{_coord}.sha256")
        if not (isinstance(_e.get("size"), int) and _e["size"] > 0):
            _bad.append(f"{_coord}.size")
        if _e.get("reason") not in ("upstream-missing", "unpublished", "local-modified", "explicit"):
            _bad.append(f"{_coord}.reason")
    chk(not _bad, "vendored 五字段合规（path/version/sha256/size/reason）"
        + (f"　不合格：{_bad[:3]}" if _bad else ""))
    chk(len(m["files"]) >= 1, "files[] 非空（pydeps 重内容）")
    if m["files"]:
        e = m["files"][0]
        chk(bool(re.match(r"^pydeps/[^/]+$", e["path"])), "files[0].path 落在 pydeps/ 内")
        # server.py 的 pydeps_dir() 按 pydeps-*.tar.gz 模式发现归档（不再硬编码版本号）；
        # 此处守住同一契约，避免归档改名后运行期找不到包（2.1.0 曾因版本失配导致离线依赖全废）。
        chk(bool(re.match(r"^pydeps/pydeps-.+\.tar\.gz$", e["path"])),
            "files[0].path 匹配 server.py 的 pydeps-*.tar.gz 发现模式")
        chk(bool(re.match(r"^[0-9a-f]{64}$", e["sha256"])), "files[0].sha256 为 64 位 hex")
        chk(isinstance(e["size"], int) and e["size"] > 0, "files[0].size 为正整数")
        chk(all(u.startswith("https://") for u in e["urls"]), "files[0].urls 为 https 地址")
        chk(any("gh-proxy.com" in u for u in e["urls"]), "files[0].urls 含国内镜像源（gh-proxy.com）")
        chk(any(u.startswith("https://github.com/") for u in e["urls"]), "files[0].urls 含 GitHub 权威源作回退")

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        inner = [n for n in names if "/" in n]
        chk("dspack.json" in names and "manifest.json" in names, "ZIP 根含 dspack.json + manifest.json")
        chk("package.json" in names and "pnpm-workspace.yaml" in names,
            "ZIP 根含机器文件 package.json + pnpm-workspace.yaml")
        chk(all(n.startswith("overrides/") or n.startswith("home/") or n.startswith("vendor/")
                for n in inner),
            "用户文件均在 overrides/、home/ 或 vendor/ 内")
        _vend = sorted(n for n in names if n.startswith("vendor/"))
        _want = sorted(e["path"] for e in (vm or {}).values())
        chk(_vend == _want, f"ZIP 的 vendor/ 与 vendored{{}} 登记一一对应（{len(_vend)} 个，规范：未登记即拒装）")
        _mism = [e["path"] for e in (vm or {}).values()
                 if len(z.read(e["path"])) != e["size"]
                 or hashlib.sha256(z.read(e["path"])).hexdigest() != e["sha256"]]
        chk(not _mism, "vendor/ 内 tarball 的 sha256 与 size 全部匹配"
            + (f"　不符：{_mism[:2]}" if _mism else ""))
        chk("overrides/wta/ui/server.py" in names, "overrides/wta/ui/server.py 存在（工作台）")
        chk("home/AGENTS.md" in names, "home/AGENTS.md 存在（全局指令）")
        skills = [n for n in names if n.startswith("home/skills/") and n.endswith("SKILL.md")]
        chk(len(skills) == 14, f"home/skills 含 14 个技能（实际 {len(skills)}）")
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
        # vendor/ → ZIP 根：manifest vendored{} 指向的依赖 tarball（离线导入用）。
        # 规范硬约束：vendor/ 内只允许 .tgz，且每个文件都必须在 vendored{} 里登记，否则导入端拒装。
        vm = manifest["vendored"]
        for entry in vm.values():
            rel = entry["path"]
            z.write(VENDOR_DIR / Path(rel).name, rel)
        print(f"  vendor/: 已打包 {len(vm)} 个依赖 tarball（离线导入）")

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
