# -*- coding: utf-8 -*-
"""
ui/server.py —— 整合包工作台本地服务（仅绑定 127.0.0.1）

设计约束（Phase 2 强制）：
- 零第三方依赖（仅 Python 标准库）；
- 只监听 127.0.0.1，不暴露局域网/公网；
- 端口 8618 起自动回退（8619、8620...）；
- 目录访问白名单（工作区根 + integration-pack），路径规范化防逃逸
  （拒绝 ../ 逃逸、绝对盘符、UNC、Windows 设备路径）；
- 工具调用白名单 + 参数数组，禁止 shell 与任意命令。

API：
  GET  /api/health    服务与路径信息
  GET  /api/env       环境状态（Python/依赖/CAD/技能/招标日报）
  GET  /api/dirs?path=<相对路径>   目录列表（白名单内）
  GET  /api/file?path=<相对路径>   文本预览（UTF-8、≤200KB、扩展名白名单）
  POST /api/explorer  {"path": "<相对路径>"}  在资源管理器中打开（白名单内）
  POST /api/run       {"tool": ..., "params": {...}}  ← Phase 2D
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

# pythonw 无控制台运行时 sys.stdout/stderr 为 None（print 会崩）——兜底到空设备。
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PACK_ROOT = Path(__file__).resolve().parent.parent          # integration-pack
UI_ROOT = Path(__file__).resolve().parent                    # integration-pack/ui
STATIC_ROOT = UI_ROOT / "static"
WORKSPACE_ROOT = PACK_ROOT.parent                            # 工作区根
WS_CONFIG_PATH = PACK_ROOT / "config" / "ui-workspace.json"  # 用户自定义工作区配置

DEFAULT_PORT = 8618
MAX_PORT_TRIES = 10

# 文本预览：扩展名白名单 + 大小上限
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".js", ".mjs",
    ".ts", ".html", ".css", ".ini", ".log", ".cmd", ".ps1", ".xml", ".toml",
}
MAX_PREVIEW_BYTES = 200 * 1024

# 环境状态缓存（秒）
ENV_CACHE_TTL = 60

# 工具白名单（normalize 已接入；Phase 4 接入其余工具）
# params schema：file=单文件 / files=多文件 / number=数值范围 / flag=布尔开关
TOOL_SPECS = {
    "normalize": {
        "script": "quote_tools.py",
        "args": ["normalize", "{input}", "--out", "{out}"],
        "params": {"input": {"kind": "file", "exts": [".xlsx", ".csv"]}},
        "out_suffix": "设备表.xlsx",
    },
    "compare": {
        "script": "quote_tools.py",
        "args": ["compare", "__INPUTS__", "--out", "{out}"],
        "params": {"inputs": {"kind": "files", "min": 2, "max": 8, "exts": [".xlsx", ".csv"]}},
        "out_suffix": "比对表.xlsx",
    },
    "cost": {
        "script": "quote_tools.py",
        "args": ["cost", "{input}", "--out", "{out}",
                 "--tax", "{tax}", "--freight", "{freight}", "--install", "{install}",
                 "--admin", "{admin}", "--profit", "{profit}", "__FLAG_ALLOW_DUP__"],
        "params": {
            "input": {"kind": "file", "exts": [".xlsx", ".csv"]},
            "tax": {"kind": "number", "default": 13, "min": 0, "max": 30},
            "freight": {"kind": "number", "default": 0, "min": 0},
            "install": {"kind": "number", "default": 0, "min": 0, "max": 100},
            "admin": {"kind": "number", "default": 5, "min": 0, "max": 100},
            "profit": {"kind": "number", "default": 8, "min": 0, "max": 100},
            "allow_duplicates": {"kind": "flag", "default": False},
        },
        "out_suffix": "测算表.xlsx",
    },
    "diff": {
        "script": "quote_tools.py",
        "args": ["diff", "{tender}", "{quote}", "--out", "{out}"],
        "params": {
            "tender": {"kind": "file", "exts": [".xlsx", ".csv"]},
            "quote": {"kind": "file", "exts": [".xlsx", ".csv"]},
        },
        "out_suffix": "差异报告.xlsx",
    },
    "dxf_parse": {
        "script": "dxf_parse.py",
        "args": ["{dxf}", "--out", "{out}"],
        "params": {"dxf": {"kind": "file", "exts": [".dxf"]}},
        "out_suffix": "提取清单.xlsx",
    },
    "cad_env": {"script": "cad_env.py", "args": ["--json"], "params": {}},
    "smoke_test": {"script": "smoke_test.py", "args": [], "params": {}, "timeout": 300},
    "bootstrap": {"script": "bootstrap_libs.py", "args": [], "params": {}, "timeout": 600},
}
RUN_TIMEOUT_SECONDS = 120

_current_run = {"proc": None, "tool": None, "started": 0.0, "cancel_requested": False}

DEVICE_NAME_RE = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.IGNORECASE
)

_env_cache = {"at": 0.0, "data": None}


def configured_workspace():
    """用户自定义工作区（config/ui-workspace.json，可随时修改）。无效或不存在时返回 None。"""
    try:
        data = json.loads(WS_CONFIG_PATH.read_text(encoding="utf-8"))
        p = data.get("path")
        if p:
            path = Path(p).resolve()
            if path.is_dir():
                return path
    except Exception:  # noqa: BLE001
        pass
    return None


def get_allowed_roots():
    """目录白名单：用户自定义工作区（若配置）+ 工作区根 + 整合包根。"""
    roots = [WORKSPACE_ROOT, PACK_ROOT]
    ws = configured_workspace()
    if ws is not None and ws not in roots:
        roots.insert(0, ws)
    return roots


def active_workspace():
    """当前工作区根：用户自定义工作区（若已配置），否则整合包父目录。"""
    return configured_workspace() or WORKSPACE_ROOT


def save_workspace(path_str):
    WS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    WS_CONFIG_PATH.write_text(
        json.dumps({"path": str(path_str)}, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def pick_directory():
    """弹 Windows 原生目录选择对话框，返回所选路径；取消返回 None。"""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description = '选择工作区目录';"
        "$d.ShowNewFolderButton = $true;"
        "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.SelectedPath }"
    )
    try:
        flags = {}
        if os.name == "nt":
            # 隐藏 PowerShell 的控制台窗口（FolderBrowserDialog 是 GUI，不受影响）
            flags["creationflags"] = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
            **flags,
        )
        path = (r.stdout or "").strip()
        return path or None
    except Exception:  # noqa: BLE001
        return None


def is_device_name(name: str) -> bool:
    return bool(DEVICE_NAME_RE.match(name or ""))


def is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def safe_resolve(request_path: str):
    """把请求路径安全解析到白名单目录内；拒绝一切逃逸。返回 Path 或 None。

    特殊前缀：`@pack/xxx` → 解析为整合包内路径（PACK_ROOT/xxx）。
    用于整合包自带资源（模板/数据/文档/脚本），跨部署布局稳定且无歧义
    （开发时 PACK_ROOT=…/integration-pack，导入后 PACK_ROOT=$DSH_HOME/wta）。
    """
    if not isinstance(request_path, str):
        return None
    if request_path == "":
        return active_workspace()  # 空路径 = 当前工作区根（用户自定义优先）
    raw = request_path.replace("\\", "/").strip()
    if raw.startswith("//") or raw.startswith("\\\\"):
        return None
    if raw == "@pack" or raw.startswith("@pack/"):
        rel = raw[len("@pack"):].lstrip("/")
        candidate = (PACK_ROOT / rel).resolve() if rel else PACK_ROOT
        return candidate if is_within(candidate, PACK_ROOT) else None
    # 绝对路径（Windows 盘符 / POSIX 根）——仅在白名单目录内接受
    if re.match(r"^[a-zA-Z]:", raw) or raw.startswith("/"):
        try:
            resolved = Path(raw).resolve()
        except OSError:
            return None
        for root in get_allowed_roots():
            if is_within(resolved, root):
                return resolved
        return None
    decoded = unquote(raw)
    parts = [p for p in decoded.split("/") if p not in ("", ".")]
    if any(is_device_name(p) for p in parts):
        return None
    for root in get_allowed_roots():
        candidate = (root / decoded).resolve()
        if is_within(candidate, root):
            return candidate
    return None


def rel_of(path: Path) -> str:
    """绝对路径 → 相对当前工作区根的斜杠路径；不在工作区下则返回绝对路径。"""
    ws = active_workspace()
    try:
        rel = path.relative_to(ws)
        return rel.as_posix()
    except ValueError:
        return path.as_posix()


def port_is_free(host: str, port: int) -> bool:
    # 注意：不使用 SO_REUSEADDR——Windows 下 SO_REUSEADDR 允许与 LISTENING 端口共存，
    # 探测会得到假空闲。无 REUSEADDR 的 bind 对已占用端口会稳定失败。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(host: str = "127.0.0.1", start: int = DEFAULT_PORT,
                   tries: int = MAX_PORT_TRIES):
    for port in range(start, start + tries):
        if port_is_free(host, port):
            return port
    raise OSError(f"no free port in range {start}..{start + tries - 1}")


# ---------- 业务只读探测（全部调用现有能力，不复制业务逻辑） ----------

def _py_run(args, timeout=15, env_extra=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PACK_ROOT / "pydeps") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    # 注意：-3 是 py 启动器的参数，sys.executable（python.exe）不识别；
    # 仅在无 sys.executable 时回退 py -3。
    cmd = [sys.executable, *args] if sys.executable else ["py", "-3", *args]
    return subprocess.run(
        cmd,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, env=env, cwd=str(PACK_ROOT),
    )


def env_status(force=False):
    now = time.time()
    if not force and _env_cache["data"] is not None and now - _env_cache["at"] < ENV_CACHE_TTL:
        return _env_cache["data"]

    data = {"python": {"ok": False, "version": ""}, "pydeps": {"ok": False, "detail": ""},
            "cad": {"dwg_to_dxf": "unknown", "has_autocad": False, "has_oda": False},
            "skills": 0, "tender_reports": 0}

    try:
        r = _py_run(["-c", "import sys; print(sys.version.split()[0])"], timeout=10)
        if r.returncode == 0:
            data["python"] = {"ok": True, "version": r.stdout.strip()}
    except Exception as e:  # noqa: BLE001
        data["python"] = {"ok": False, "version": str(e)[:80]}

    try:
        r = _py_run(["-c", "import openpyxl, pandas, ezdxf; print('ok')"], timeout=20)
        data["pydeps"] = {"ok": r.returncode == 0,
                          "detail": r.stdout.strip() if r.returncode == 0 else (r.stderr or r.stdout).strip()[:120]}
    except Exception as e:  # noqa: BLE001
        data["pydeps"] = {"ok": False, "detail": str(e)[:120]}

    try:
        r = _py_run([str(PACK_ROOT / "scripts" / "cad_env.py"), "--json"], timeout=20)
        if r.returncode == 0:
            cad = json.loads(r.stdout)
            data["cad"] = {
                "dwg_to_dxf": cad.get("dwg_to_dxf", "unknown"),
                "has_autocad": cad.get("autocad") is not None,
                "has_oda": cad.get("oda") is not None,
            }
    except Exception:  # noqa: BLE001
        pass

    skills_dir = PACK_ROOT / "skills"
    if skills_dir.is_dir():
        data["skills"] = len(list(skills_dir.glob("*/SKILL.md")))
    tender_dir = PACK_ROOT / "reports" / "tender"
    if tender_dir.is_dir():
        data["tender_reports"] = len(list(tender_dir.glob("*.md")))

    _env_cache["at"] = now
    _env_cache["data"] = data
    return data


def list_dir_json(rel: str):
    target = safe_resolve(rel)
    if target is None:
        return None
    if not target.exists():
        return {"rel": rel, "exists": False, "entries": []}
    if not target.is_dir():
        return {"rel": rel, "exists": True, "is_dir": False, "entries": []}
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        try:
            entries.append({
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
                "rel": rel_of(child),
            })
        except OSError:
            continue
    return {"rel": rel, "exists": True, "is_dir": True, "entries": entries}


def preview_file_json(rel: str):
    target = safe_resolve(rel)
    if target is None:
        return None
    if not target.exists() or not target.is_file():
        return {"rel": rel, "exists": False}
    ext = target.suffix.lower()
    # 二进制办公文档：xlsx/docx 走结构化解包预览（大小上限放宽到 5MB）
    if ext in (".xlsx", ".xlsm"):
        return preview_xlsx(target, rel)
    if ext == ".docx":
        return preview_docx(target, rel)
    if ext == ".doc":
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "旧版 .doc 为二进制 OLE 格式，暂不支持在线预览。请用 Word 另存为 .docx 后再预览。"}
    if ext not in TEXT_EXTENSIONS:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "该类型不支持预览（请用资源管理器打开）"}
    if target.stat().st_size > MAX_PREVIEW_BYTES:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "文件过大（超过 200KB），请用资源管理器打开"}
    raw = target.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "非 UTF-8 文本或二进制文件，不支持预览"}
    return {"rel": rel, "exists": True, "previewable": True,
            "content": text, "kind": "md" if ext == ".md" else "text"}


def preview_xlsx(target, rel):
    if target.stat().st_size > 5 * 1024 * 1024:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "工作簿过大（超过 5MB），请用资源管理器打开"}
    try:
        sys.path.insert(0, str(PACK_ROOT / "pydeps"))
        import openpyxl  # noqa: PLC0415
        wb = openpyxl.load_workbook(target, data_only=True)
    except ImportError:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "预览组件缺失：请在工具页运行“重建依赖库”。"}
    except Exception as e:  # noqa: BLE001
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": f"无法预览该工作簿：{e}"}
    try:
        lines = []
        for ws in wb.worksheets[:3]:
            lines.append(f"## Sheet: {ws.title}")
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                cells = ["" if c is None else str(c) for c in row]
                lines.append("\t".join(cells))
                if i >= 59:
                    lines.append("…（仅显示前 60 行）")
                    break
        wb.close()
        return {"rel": rel, "exists": True, "previewable": True,
                "content": "\n".join(lines), "kind": "table"}
    except Exception as e:  # noqa: BLE001
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": f"读取工作簿失败：{e}"}


def preview_docx(target, rel):
    if target.stat().st_size > 5 * 1024 * 1024:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "文档过大（超过 5MB），请用资源管理器打开"}
    try:
        sys.path.insert(0, str(PACK_ROOT / "pydeps"))
        import docx  # noqa: PLC0415
        d = docx.Document(str(target))
        paras = [p.text for p in d.paragraphs if p.text.strip()]
        content = "\n\n".join(paras[:200])
        return {"rel": rel, "exists": True, "previewable": True,
                "content": content or "（文档无文本内容）", "kind": "text"}
    except ImportError:
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": "预览组件缺失：请在工具页运行“重建依赖库”。"}
    except Exception as e:  # noqa: BLE001
        return {"rel": rel, "exists": True, "previewable": False,
                "reason": f"无法预览该文档：{e}"}


def open_in_explorer(rel: str):
    target = safe_resolve(rel)
    if target is None:
        return False
    if not target.exists():
        return False
    try:
        if target.is_dir():
            subprocess.Popen(["explorer", str(target)])
        else:
            subprocess.Popen(["explorer", "/select,", str(target)])
        return True
    except OSError:
        return False


# ---------- 工具运行（白名单 + 参数数组 + 无 shell） ----------

def _build_run(tool, params):
    """校验工具与参数，构造参数数组。返回 (构建结果, 错误信息)。"""
    spec = TOOL_SPECS.get(tool)
    if spec is None:
        return None, "未知工具（可用：normalize / compare / cost / diff / dxf_parse / cad_env / smoke_test / bootstrap）"
    if not isinstance(params, dict):
        params = {}
    values = {}
    for name, p in spec.get("params", {}).items():
        if p["kind"] == "file":
            raw = params.get(name)
            if not isinstance(raw, str) or raw == "":
                return None, f"缺少输入文件路径（{name}）"
            target = safe_resolve(raw)
            if target is None:
                return None, f"输入路径不在允许范围内（{name}）"
            if not target.is_file():
                return None, f"输入文件不存在（{name}）"
            ext = target.suffix.lower()
            if ext not in p["exts"]:
                return None, f"不支持的文件类型 {ext}（{name}，支持：{' / '.join(p['exts'])}）"
            values[name] = str(target)
        elif p["kind"] == "files":
            raw = params.get(name)
            if not isinstance(raw, list) or not (p["min"] <= len(raw) <= p["max"]):
                return None, f"需要 {p['min']}~{p['max']} 个输入文件（{name}）"
            vals = []
            for r in raw:
                if not isinstance(r, str):
                    return None, f"输入路径必须是字符串（{name}）"
                t = safe_resolve(r)
                if t is None:
                    return None, f"输入路径不在允许范围内（{name}）"
                if not t.is_file():
                    return None, f"输入文件不存在（{name}：{r}）"
                if t.suffix.lower() not in p["exts"]:
                    return None, f"不支持的文件类型 {t.suffix}（{name}）"
                vals.append(str(t))
            values[name] = vals
        elif p["kind"] == "number":
            raw = params.get(name, p.get("default"))
            try:
                num = float(raw)
            except (TypeError, ValueError):
                return None, f"参数 {name} 必须是数字"
            if "min" in p and num < p["min"]:
                return None, f"参数 {name} 不能小于 {p['min']}"
            if "max" in p and num > p["max"]:
                return None, f"参数 {name} 不能大于 {p['max']}"
            values[name] = num
        elif p["kind"] == "flag":
            values[name] = bool(params.get(name, p.get("default")))
    # 输出路径
    out_path = None
    if "out_suffix" in spec:
        out_dir = PACK_ROOT / "reports" / "ui"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = values.get("input") or values.get("dxf") or values.get("tender") or "run"
        out_path = out_dir / f"{tool}_{stamp}_{Path(base).stem}_{spec['out_suffix']}"
        values["out"] = str(out_path)
    # 参数数组（无 shell）
    script = PACK_ROOT / "scripts" / spec["script"]
    args = [sys.executable, str(script)]
    for a in spec["args"]:
        if a == "__INPUTS__":
            args.extend(values.get("inputs", []))
        elif a == "__FLAG_ALLOW_DUP__":
            if values.get("allow_duplicates"):
                args.append("--allow-duplicates")
        else:
            args.append(a.format(**values))
    return {"proc_args": args, "out_path": out_path, "tool": tool,
            "timeout": spec.get("timeout", RUN_TIMEOUT_SECONDS)}, None


def execute_run(tool, params):
    """执行白名单工具（参数数组、无 shell），支持超时与取消。"""
    global _current_run
    built, err = _build_run(tool, params or {})
    if err is not None:
        return {"status": "rejected", "error": err}
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PACK_ROOT / "pydeps") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        built["proc_args"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(PACK_ROOT),
    )
    _current_run["proc"] = proc
    _current_run["tool"] = tool
    _current_run["started"] = time.time()
    _current_run["cancel_requested"] = False
    deadline = time.time() + built.get("timeout", RUN_TIMEOUT_SECONDS)
    cancelled = False
    stdout_str, stderr_str = "", ""
    try:
        while proc.poll() is None:
            if _current_run["cancel_requested"]:
                _current_run["cancel_requested"] = False
                proc.terminate()
                try:
                    stdout_str, stderr_str = proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout_str, stderr_str = proc.communicate()
                cancelled = True
                break
            if time.time() > deadline:
                proc.kill()
                stdout_str, stderr_str = proc.communicate()
                return {"status": "timeout", "tool": tool,
                        "stdout": stdout_str,
                        "stderr": f"操作超过 {int(built.get('timeout', RUN_TIMEOUT_SECONDS))} 秒，已终止。"}
            time.sleep(0.2)
        if not cancelled:
            stdout_str, stderr_str = proc.communicate()
    finally:
        _current_run["proc"] = None
        _current_run["tool"] = None
    exit_code = proc.returncode
    out_rel = rel_of(built["out_path"]) if built.get("out_path") and built["out_path"].exists() else None
    return {
        "status": "cancelled" if cancelled else ("ok" if exit_code == 0 else "failed"),
        "tool": tool,
        "exit_code": exit_code,
        "stdout": stdout_str,
        "stderr": stderr_str,
        "output": out_rel,
    }


def _json_response(handler, status: int, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class UiHandler(BaseHTTPRequestHandler):
    server_version = "IntegrationPackWorkbench/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[ui] %s\n" % (fmt % args))

    def _send_text(self, status: int, text: str, content_type: str):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path == "/api/health":
            return _json_response(self, 200, {
                "status": "ok",
                "name": "integration-pack-workbench",
                "workspace": str(configured_workspace()) if configured_workspace() else "",
                "pack_root": str(PACK_ROOT),
            })
        if path == "/api/workspace":
            return _json_response(self, 200, {
                "workspace": str(configured_workspace()) if configured_workspace() else "",
                "custom": configured_workspace() is not None,
            })
        if path == "/api/env":
            return _json_response(self, 200, env_status(force=query.get("refresh") == ["1"]))
        if path == "/api/dirs":
            rel = query.get("path", [""])[0]
            data = list_dir_json(rel)
            if data is None:
                return _json_response(self, 403, {"error": "forbidden", "path": rel})
            if not data.get("exists"):
                return _json_response(self, 404, {"error": "not found", "path": rel,
                                                  "hint": "目录不存在。可点击“创建目录”或检查路径。"})
            return _json_response(self, 200, data)
        if path == "/api/file":
            rel = query.get("path", [""])[0]
            data = preview_file_json(rel)
            if data is None:
                return _json_response(self, 403, {"error": "forbidden", "path": rel})
            if not data.get("exists"):
                return _json_response(self, 404, {"error": "not found", "path": rel,
                                                  "hint": "文件不存在。"})
            return _json_response(self, 200, data)
        if path.startswith("/api/"):
            return _json_response(self, 404, {"error": "not found", "path": path})

        # 静态文件
        rel = path.lstrip("/") or "index.html"
        target = (STATIC_ROOT / rel).resolve()
        if not is_within(target, STATIC_ROOT):
            return _json_response(self, 403, {"error": "forbidden"})
        if not target.is_file():
            return self._send_text(404, "未找到该页面。", "text/plain")
        content = target.read_bytes()
        self.send_response(200)
        ctype = "text/html" if target.suffix == ".html" else (
            "text/css" if target.suffix == ".css" else
            "application/javascript" if target.suffix == ".js" else
            "application/octet-stream"
        )
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _json_response(self, 400, {"error": "bad json"})

        if path == "/api/workspace/pick":
            picked = pick_directory()
            if picked:
                return _json_response(self, 200, {"ok": True, "path": picked})
            return _json_response(self, 200, {"ok": False, "path": None})
        if path == "/api/workspace":
            raw = payload.get("path")
            if not isinstance(raw, str) or raw.strip() == "":
                return _json_response(self, 400, {"error": "path must be a non-empty string"})
            try:
                resolved = Path(raw).resolve()
            except OSError:
                return _json_response(self, 400, {"error": "invalid path"})
            if not resolved.is_dir():
                return _json_response(self, 400, {
                    "error": "directory does not exist",
                    "hint": "目录不存在，请检查后重试（不会创建目录）。",
                })
            save_workspace(resolved)
            return _json_response(self, 200, {"ok": True, "workspace": str(resolved)})
        if path == "/api/shutdown":
            _json_response(self, 200, {"ok": True, "message": "工作台已停止，请关闭浏览器页面。"})

            def _stop():
                time.sleep(0.5)
                threading.Thread(target=self.server.shutdown, daemon=True).start()

            threading.Timer(0.1, _stop).start()
            return
        if path == "/api/explorer":
            rel = payload.get("path", "")
            if not isinstance(rel, str):
                return _json_response(self, 400, {"error": "path must be a string"})
            ok = open_in_explorer(rel)
            if not ok:
                return _json_response(self, 404, {
                    "error": "not found or forbidden",
                    "hint": "目录不存在，或不在允许范围内。",
                })
            return _json_response(self, 200, {"ok": True})
        if path == "/api/run":
            tool = payload.get("tool")
            params = payload.get("params")
            if not isinstance(params, dict):
                return _json_response(self, 400, {"error": "params must be an object"})
            result = execute_run(tool, params)
            status = 400 if result.get("status") == "rejected" else 200
            return _json_response(self, status, result)
        if path == "/api/cancel":
            if _current_run["proc"] is None:
                return _json_response(self, 200, {"ok": False, "error": "当前没有正在运行的任务"})
            _current_run["cancel_requested"] = True
            return _json_response(self, 200, {"ok": True})
        if path == "/api/mkdir":
            rel = payload.get("path", "")
            if not isinstance(rel, str) or rel == "":
                return _json_response(self, 400, {"error": "path must be a non-empty string"})
            target = safe_resolve(rel)
            if target is None:
                return _json_response(self, 403, {"error": "forbidden", "path": rel})
            if target.exists():
                return _json_response(self, 409, {"error": "already exists", "path": rel})
            try:
                target.mkdir(parents=True)
            except OSError as e:
                return _json_response(self, 500, {"error": "mkdir failed",
                                                  "detail": str(e)})
            return _json_response(self, 200, {"ok": True, "rel": rel_of(target)})
        return _json_response(self, 404, {"error": "not found", "path": path})


def create_server(port: int = None, host: str = "127.0.0.1"):
    actual_port = port if port is not None else find_free_port(host)
    return ThreadingHTTPServer((host, actual_port), UiHandler), actual_port


def main():
    argv = sys.argv[1:]
    port_file = None
    pid_file = None
    port = None
    open_browser = "--open" in argv
    if "--port-file" in argv:
        i = argv.index("--port-file") + 1
        if i < len(argv):
            port_file = Path(argv[i])
    if "--pid-file" in argv:
        i = argv.index("--pid-file") + 1
        if i < len(argv):
            pid_file = Path(argv[i])
    if "--port" in argv:
        i = argv.index("--port") + 1
        if i < len(argv):
            port = int(argv[i])
    if port is None:
        port = find_free_port("127.0.0.1")
    server = ThreadingHTTPServer(("127.0.0.1", port), UiHandler)
    if port_file is not None:
        port_file.write_text(str(port), encoding="utf-8")
    if pid_file is not None:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    print(f"工作台已启动：http://127.0.0.1:{port}  （仅本机可访问，Ctrl+C 停止）")
    print(f"工作区：{WORKSPACE_ROOT}")
    print(f"整合包：{PACK_ROOT}")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:  # noqa: BLE001
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
