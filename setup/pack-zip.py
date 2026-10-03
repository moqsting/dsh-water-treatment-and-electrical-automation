import zipfile, os, json, hashlib
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
VERSION = json.loads((SRC / "pack.json").read_text(encoding="utf-8"))["version"]
OUT = SRC / "release" / f"water-treatment-and-electrical-automation-v{VERSION}.zip"
OUT.parent.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {"__pycache__", ".git", ".npm-cache", "node_modules", "release", "dist"}
EXCLUDE_FILES = {"ui-workspace.json", "cad_env.json"}

def should_include(rel: str):
    parts = rel.split("/")
    # reports/tender/* 与 reports/ui/* 只保留 .gitkeep（运行产物不打包）
    if len(parts) >= 3 and parts[0] == "reports" and parts[1] in ("tender", "ui"):
        return parts[2] == ".gitkeep"
    return True

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f in EXCLUDE_FILES:
                continue
            p = Path(root) / f
            rel = p.relative_to(SRC).as_posix()
            if not should_include(rel):
                continue
            z.write(p, rel)
            count += 1

print("打包完成:", OUT)
print("文件数:", count)
print("大小: %.1f MB" % (OUT.stat().st_size / 1048576))

# 验证关键文件
with zipfile.ZipFile(OUT) as z:
    names = set(z.namelist())
    checks = ["ui/server.py", "ui/start.pyw", "setup/一键安装.cmd", "setup/install.ps1",
              "setup/make-dspack.py", "setup/deploy-to-instance.py", "skills/plc-programming-assist/SKILL.md",
              "plugins/open-workbench/client.js", "plugins/open-workbench/index.js",
              "README.md", "CHANGELOG.md", "pack.json", "LICENSE", "AGENTS.md"]
    for c in checks:
        print(("  OK  " if c in names else "  MISSING  ") + c)
    print("  含 __pycache__:", any("__pycache__" in n for n in names))
    print("  含 ui-workspace.json:", "config/ui-workspace.json" in names)

# 生成校验文件（GitHub Release 附件用）
digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
(OUT.with_suffix(".zip.sha256")).write_text(f"{digest}  {OUT.name}\n", encoding="utf-8")
print("SHA256:", digest)