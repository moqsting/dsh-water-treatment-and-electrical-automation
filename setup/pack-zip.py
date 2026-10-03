import zipfile, os
from pathlib import Path

SRC = Path(r"D:\DeepSeek Harness\integration-pack")
OUT = Path(r"D:\Download\water-treatment-and-electrical-automation-v1.0.0.zip")

EXCLUDE_DIRS = {"__pycache__", ".git", ".npm-cache", "node_modules"}
EXCLUDE_FILES = {"ui-workspace.json", "cad_env.json"}

def should_include(rel: str):
    parts = rel.split("/")
    # reports/tender/* 与 reports/ui/* 只保留 .gitkeep（运行产物不打包）
    if len(parts) >= 3 and parts[0] == "reports" and parts[1] in ("tender", "ui"):
        return parts[2] == ".gitkeep"
    return True

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
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
              "plugins/open-workbench/client.js", "README.md", "pack.json", "LICENSE", "AGENTS.md"]
    for c in checks:
        print(("  OK  " if c in names else "  MISSING  ") + c)
    print("  含 __pycache__:", any("__pycache__" in n for n in names))
    print("  含 ui-workspace.json:", "config/ui-workspace.json" in names)