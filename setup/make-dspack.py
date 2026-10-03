# -*- coding: utf-8 -*-
r"""setup/make-dspack.py —— 生成 DSH 整合包（.dspack v3 / manifest v5）

依据 DSH-PackForge 现行规范：
  - specs/manifest/v5.md      （type=dshhome：defaultProfile + profiles 对象 + skills[]）
  - specs/pack-structure/v3.md（纯 ZIP + 根 dspack.json；dshhome 形态 overrides/ 按 $DSH_HOME 平铺）

用法：
  py -3 setup\make-dspack.py            # 输出到 release/<name>-<version>.dspack
  py -3 setup\make-dspack.py --out DIR  # 指定输出目录

内容：把 skills/<name>/SKILL.md 打进 overrides/skills/<name>/SKILL.md（即 $DSH_HOME/skills/...）。
脚本、工作台、离线依赖不属于 DSH_HOME 结构，由 setup/一键安装.cmd 负责，不进本包。
"""
import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
NAME = "water-treatment-and-electrical-automation"
VERSION = "1.2.0"
PROFILE_NAME = "wet-automation"          # 不得为 web / headless（规范硬约束）
DSH_VERSION = "0.2.0-rc.2"


def build_manifest(skill_dirs):
    return {
        "manifestVersion": 5,
        "type": "dshhome",
        "name": NAME,
        "version": VERSION,
        "displayName": {
            "zh-CN": "水处理与电气自动化整合包",
            "en-US": "Water Treatment & Electrical Automation Pack",
        },
        "description": {
            "zh-CN": "水处理与电气自动化工程师整合包：PLC 程序开发辅助、投标报价清单处理、招标与价格查询、"
                     "CAD 识图、水处理工艺计算、电气设计计算、规范标准查询、打开工作台、故障诊断（共 9 个技能）。",
            "en-US": "Integration pack for water-treatment and electrical-automation engineers (9 skills).",
        },
        "author": "moqsting",
        "icon": "",
        "dshVersion": DSH_VERSION,
        "defaultProfile": PROFILE_NAME,
        "profiles": {
            PROFILE_NAME: {
                "bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", "dsh-open-workbench"],
                "dependencies": {"dsh-open-workbench": "file:open-workbench"},
            }
        },
        "instructions": "AGENTS.md",
        "skills": [{"path": f"skills/{d.name}"} for d in skill_dirs],
    }


def self_check(manifest, zip_path):
    """按规范硬约束自检，返回 (是否通过, 明细列表)。"""
    lines = []

    def chk(cond, msg):
        lines.append(("PASS" if cond else "FAIL") + "  " + msg)
        return bool(cond)

    ok = True
    m = manifest
    ok &= chk(m["manifestVersion"] == 5, "manifestVersion == 5")
    ok &= chk(m["type"] in ("profile", "dshhome"), f"type 合法（{m['type']}）")
    ok &= chk(bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", m["name"])), "name 为 kebab-case")
    ok &= chk(bool(re.match(r"^\d+\.\d+\.\d+$", m["version"])), "version 为 semver")
    ok &= chk(isinstance(m["profiles"], dict) and len(m["profiles"]) >= 1, "profiles 为对象且非空")
    ok &= chk(all(k not in ("web", "headless") for k in m["profiles"]), "profiles 不含 web/headless")
    ok &= chk(m["defaultProfile"] in m["profiles"], "defaultProfile 指向存在的 profile key")
    ok &= chk(all("bundles" in v and "dependencies" in v for v in m["profiles"].values()),
              "每个 ProfileUnit 含 bundles + dependencies")
    ok &= chk(all(s["path"].startswith("skills/") for s in m.get("skills", [])),
              "skills[].path 相对 $DSH_HOME")
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        inner = [n for n in names if "/" in n]
        ok &= chk("dspack.json" in names and "manifest.json" in names, "ZIP 根含 dspack.json + manifest.json")
        ok &= chk(all(n.startswith("overrides/") for n in inner), "用户文件均在 overrides/ 内")
        ok &= chk(not any(n.startswith("overrides/home/") for n in names),
                  "dshhome 形态：overrides/ 直接平铺（无 home/ 前缀，即 profile 形态误用）")
        # 只统计 home 级技能（overrides/skills/）；overrides/wta/skills/ 是供 @pack/skills 浏览的副本
        ok &= chk(len([n for n in names
                       if n.startswith("overrides/skills/") and n.endswith("SKILL.md")]) == len(m.get("skills", [])),
                  f"技能文件数与 manifest.skills 一致（{len(m.get('skills', []))}）")
        ok &= chk("overrides/AGENTS.md" in names, "含全局指令 AGENTS.md")
        ok &= chk("overrides/wta/ui/server.py" in names, "含工作台 ui（overrides/wta/ui/server.py）")
        ok &= chk(any(n.startswith("overrides/wta/pydeps/") for n in names), "含离线依赖 pydeps（工具可离线运行）")
        ok &= chk("overrides/wta/README.md" in names, "含操作手册（@pack/README.md 可访问）")
        ok &= chk(any(n.startswith("overrides/wta/docs/") for n in names), "含文档目录（@pack/docs 可访问）")
        ok &= chk("overrides/wta/plugins/插件清单.md" in names, "含插件清单（@pack/plugins 可访问）")
        ok &= chk(any(n.startswith("overrides/wta/skills/") for n in names), "含技能说明（@pack/skills 可访问）")
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PACK_ROOT / "release"), help="输出目录")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    skill_dirs = sorted([p.parent for p in (PACK_ROOT / "skills").glob("*/SKILL.md")])
    if not skill_dirs:
        sys.exit("[ERROR] 未找到 skills/*/SKILL.md")
    manifest = build_manifest(skill_dirs)
    dspack = out_dir / f"{NAME}-{VERSION}.dspack"
    if dspack.exists():
        dspack.unlink()

    with zipfile.ZipFile(dspack, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dspack.json", '{"format":"dspack","version":3}')
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        # 全局指令（instructions 字段指向 AGENTS.md）
        agents = PACK_ROOT / "AGENTS.md"
        if agents.is_file():
            z.writestr("overrides/AGENTS.md", agents.read_text(encoding="utf-8"))
        # 技能（overrides/skills/<name>/SKILL.md）
        for d in skill_dirs:
            z.writestr(f"overrides/skills/{d.name}/SKILL.md",
                       (d / "SKILL.md").read_text(encoding="utf-8"))
        # 侧边栏按钮插件（本地 npm 包，挂到 profile，由 pnpm install 链接）
        plugin_dir = PACK_ROOT / "plugins" / "open-workbench"
        for f in ("package.json", "index.js", "client.js", "cordis.patch.yml"):
            p = plugin_dir / f
            if p.is_file():
                z.writestr(f"overrides/profiles/{PROFILE_NAME}/open-workbench/{f}",
                           p.read_text(encoding="utf-8"))
        # workbench-path.json：留空占位，插件会自动定位到 $DSH_HOME/wta/ui
        z.writestr(f"overrides/profiles/{PROFILE_NAME}/open-workbench/workbench-path.json",
                   '{"uiDir": "", "pythonw": "pythonw"}')
        # 工具链（工作台 + 脚本 + 离线依赖 + 模板/数据/配置 + 文档/插件/技能说明/运行目录）
        # → $DSH_HOME/wta/。目的：只发 .dspack 即可一键导入并完整可用。
        tool_dirs = ("ui", "scripts", "pydeps", "templates", "data", "config",
                     "docs", "plugins", "reports", "setup", "skills")
        skip_dirs = {"__pycache__", ".git", "vendor"}  # vendor 含 ~49MB 插件包，不随 .dspack
        skip_files = {"ui-workspace.json", "cad_env.json"}
        skip_prefix = ("reports/tender/", "reports/ui/")  # 运行产物不打包
        for d in tool_dirs:
            base = PACK_ROOT / d
            if not base.is_dir():
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [x for x in dirs if x not in skip_dirs]
                for f in files:
                    if f in skip_files:
                        continue
                    p = Path(root) / f
                    rel = p.relative_to(PACK_ROOT).as_posix()
                    if any(rel.startswith(pre) and not rel.endswith(".gitkeep") for pre in skip_prefix):
                        continue
                    z.write(p, "overrides/wta/" + rel)
        # 整合包顶层文件（README/清单/许可等，供 @pack/ 直接引用）
        for f in ("README.md", "pack.json", "LICENSE", ".gitignore", "AGENTS.md"):
            p = PACK_ROOT / f
            if p.is_file():
                z.write(p, "overrides/wta/" + f)

    ok, lines = self_check(manifest, dspack)
    print(f"输出：{dspack}  （{os.path.getsize(dspack)} 字节，{len(skill_dirs)} 个技能）")
    for line in lines:
        print("  " + line)
    print("自检：", "全部通过" if ok else "存在失败项")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
