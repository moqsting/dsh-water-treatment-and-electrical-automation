# -*- coding: utf-8 -*-
"""
cad_env.py —— CAD 环境自动探测（AutoCAD / ODA File Converter 路径查找）

用途：自动查找本机 AutoCAD（acad.exe / accoreconsole.exe）与 ODA File Converter，
判断 DWG→DXF 转换能力，并记忆用户手动指定的路径。

探测顺序：
1. Windows 注册表：HKLM/HKCU \\SOFTWARE\\Autodesk\\AutoCAD\\R<版本>\\AcadLocation
2. 常见安装路径枚举（C:/D:/Program Files/Autodesk/AutoCAD 20xx）
3. ODA File Converter：注册表 + 常见路径
4. 配置文件记忆：integration-pack/config/cad_env.json（含用户手动指定）

用法：
    runpy.cmd cad_env.py               # 探测并打印结果，更新 config/cad_env.json
    runpy.cmd cad_env.py --json        # 仅输出 JSON
"""
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import winreg
except ImportError:
    winreg = None  # 非 Windows 平台

PACK_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PACK_ROOT / "config" / "cad_env.json"

# 常见安装路径模板（按版本年份降序尝试）
AUTOCAD_DIR_TEMPLATES = [
    "C:/Program Files/Autodesk/AutoCAD {year}",
    "D:/Program Files/Autodesk/AutoCAD {year}",
    "C:/Program Files (x86)/Autodesk/AutoCAD {year}",
    "E:/Program Files/Autodesk/AutoCAD {year}",
]
ODA_DIR_TEMPLATES = [
    "C:/Program Files/ODA",
    "D:/Program Files/ODA",
    "C:/Program Files (x86)/ODA",
]


def _registry_acad_locations():
    """通过注册表查找 AutoCAD 安装路径，返回 [(version, path), ...]"""
    found = []
    if winreg is None:
        return found
    for hive, flag in ((winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
                       (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
                       (winreg.HKEY_CURRENT_USER, 0)):
        try:
            base = winreg.OpenKey(hive, r"SOFTWARE\Autodesk\AutoCAD", 0, winreg.KEY_READ | flag)
        except OSError:
            continue
        try:
            i = 0
            while True:
                try:
                    ver = winreg.EnumKey(base, i)
                    i += 1
                except OSError:
                    break
                try:
                    sub = winreg.OpenKey(base, ver, 0, winreg.KEY_READ | flag)
                    loc, _ = winreg.QueryValueEx(sub, "AcadLocation")
                    winreg.CloseKey(sub)
                    found.append((ver, loc))
                except OSError:
                    pass
        finally:
            winreg.CloseKey(base)
    return found


def _odacity_registry():
    """通过注册表查找 ODA File Converter，返回路径列表"""
    found = []
    if winreg is None:
        return found
    for hive, flag in ((winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
                       (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY)):
        for key in (r"SOFTWARE\Open Design Alliance\ODAFileConverter",
                    r"SOFTWARE\ODA\ODAFileConverter"):
            try:
                k = winreg.OpenKey(hive, key, 0, winreg.KEY_READ | flag)
                loc, _ = winreg.QueryValueEx(k, "InstallDir")
                winreg.CloseKey(k)
                found.append(loc)
            except OSError:
                pass
    return found


def _scan_common_dirs():
    """按常见路径模板扫描 AutoCAD 安装目录"""
    dirs = []
    for year in range(2028, 2012, -1):
        for tpl in AUTOCAD_DIR_TEMPLATES:
            p = Path(tpl.format(year=year))
            if p.is_dir():
                dirs.append(p)
    return dirs


def _load_saved_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def probe():
    """探测 CAD 环境，返回结构化的探测报告。"""
    saved = _load_saved_config()
    report = {
        "autocad": None,        # {"version", "dir", "acad_exe", "core_console"}
        "oda": None,            # {"dir", "exe"}
        "manual_autocad_dir": saved.get("manual_autocad_dir"),
        "manual_oda_dir": saved.get("manual_oda_dir"),
        "dwg_to_dxf": "none",   # none / autocad / autocad-acad / oda
        "hints": [],
    }

    candidates = []  # (kind, version, dir)
    for ver, loc in _registry_acad_locations():
        candidates.append(("autocad", ver, Path(loc)))
    for d in _scan_common_dirs():
        candidates.append(("autocad", d.name.replace("AutoCAD ", ""), d))
    if saved.get("manual_autocad_dir"):
        candidates.append(("autocad", "manual", Path(saved["manual_autocad_dir"])))

    for kind, ver, d in candidates:
        acad = d / "acad.exe"
        console = d / "accoreconsole.exe"
        if acad.exists() or console.exists():
            report["autocad"] = {
                "version": ver,
                "dir": str(d),
                "acad_exe": str(acad) if acad.exists() else None,
                "core_console": str(console) if console.exists() else None,
            }
            break

    oda_dirs = [Path(p) for p in _odacity_registry()]
    for tpl in ODA_DIR_TEMPLATES:
        p = Path(tpl)
        if p.is_dir():
            oda_dirs.append(p)
    if saved.get("manual_oda_dir"):
        oda_dirs.append(Path(saved["manual_oda_dir"]))
    for d in oda_dirs:
        exe = d / "ODAFileConverter.exe"
        if exe.exists():
            report["oda"] = {"dir": str(d), "exe": str(exe)}
            break

    if report["autocad"] and report["autocad"]["core_console"]:
        report["dwg_to_dxf"] = "autocad"
    elif report["autocad"] and report["autocad"]["acad_exe"]:
        report["dwg_to_dxf"] = "autocad-acad"  # 有 acad.exe 但无核心控制台
        report["hints"].append("未找到 accoreconsole.exe，可用 AutoCAD 打开后另存为 DXF 2018。")
    elif report["oda"]:
        report["dwg_to_dxf"] = "oda"
    else:
        report["hints"].extend([
            "未找到 AutoCAD 或 ODA File Converter。",
            "方案1：安装免费 ODA File Converter（https://www.opendesign.com/guestfiles/oda_file_converter），"
            "装好后重跑本脚本，或用 --set-oda <安装目录> 记忆路径。",
            "方案2：目标机器装有 AutoCAD 时，把 integration-pack 整个目录拷贝过去，"
            "用 --set-autocad <安装目录> 记忆路径（例如 C:/Program Files/Autodesk/AutoCAD 2024）。",
            "方案3：无法转换时，把图纸打印为 PDF，由 DSH 用 OCR 兜底识别。",
        ])

    return report


def main():
    as_json = "--json" in sys.argv
    if "--set-autocad" in sys.argv:
        i = sys.argv.index("--set-autocad") + 1
        if i < len(sys.argv):
            cfg = _load_saved_config()
            cfg["manual_autocad_dir"] = sys.argv[i]
            _save_config(cfg)
            print(f"已记忆 AutoCAD 目录：{sys.argv[i]}")
            return
    if "--set-oda" in sys.argv:
        i = sys.argv.index("--set-oda") + 1
        if i < len(sys.argv):
            cfg = _load_saved_config()
            cfg["manual_oda_dir"] = sys.argv[i]
            _save_config(cfg)
            print(f"已记忆 ODA 目录：{sys.argv[i]}")
            return

    report = probe()
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=" * 56)
        print("CAD 环境探测报告")
        print("=" * 56)
        if report["autocad"]:
            a = report["autocad"]
            print(f"[AutoCAD] 版本 {a['version']}  @ {a['dir']}")
            print(f"    acad.exe:        {a['acad_exe'] or '未找到'}")
            print(f"    accoreconsole:   {a['core_console'] or '未找到'}")
        else:
            print("[AutoCAD] 未找到")
        if report["oda"]:
            print(f"[ODA File Converter] @ {report['oda']['dir']}")
        else:
            print("[ODA File Converter] 未找到")
        print(f"[DWG→DXF 转换能力] {report['dwg_to_dxf']}")
        if report["hints"]:
            print("-" * 56)
            for h in report["hints"]:
                print("提示：" + h)
        print("=" * 56)


if __name__ == "__main__":
    main()
