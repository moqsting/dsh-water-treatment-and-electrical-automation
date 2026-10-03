# setup/install.ps1 —— 目标机一键部署
# 用法（在整合包根目录，右键"使用 PowerShell 运行"或）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup\install.ps1
# 完成：① Python 检查 ② 离线依赖安装 ③ 冒烟测试 ④ 技能安装（复制到 DSH 技能目录）
#       ⑤ 桌面快捷方式
# 之后在 DSH 对话中说"导入整合包自动化"完成定时任务导入（见 import-into-dsh.md）。
param(
  [string]$SkillsDir = $env:DSH_HOME   # 若 DSH_HOME 未设置，请手动传参：-SkillsDir "C:\Users\<你>\.dsh-packs\<profile>"
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot   # 整合包根目录

Write-Host "=== 整合包部署：water-treatment-and-electrical-automation ==="

# 1. Python 检查
Write-Host "[1/5] 检查 Python 3.12 ……"
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { throw "未找到 py 启动器。请安装 Python 3.12（安装时勾选 py launcher）后重试。" }
$ver = & py -3 -c "import sys; print(sys.version.split()[0])" 2>$null
if (-not $ver) { throw "py -3 不可用。请确认已安装 Python 3。" }
Write-Host "  Python $ver OK"

# 2. 离线依赖安装
Write-Host "[2/5] 安装离线依赖库（pydeps）……"
& py -3 (Join-Path $Root "scripts\bootstrap_libs.py")
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败，请检查网络与 pydeps 完整性。" }

# 3. 冒烟测试
Write-Host "[3/5] 运行整体自检（smoke_test）……"
& (Join-Path $Root "scripts\runpy.cmd") (Join-Path $Root "scripts\smoke_test.py")
if ($LASTEXITCODE -ne 0) { Write-Host "  自检未全部通过（详见输出），可继续安装；建议先排查失败项。" }

# 4. 技能安装（复制到 DSH 技能目录）
Write-Host "[4/5] 安装技能……"
if (-not $SkillsDir -or -not (Test-Path $SkillsDir)) {
  Write-Host "  未提供 DSH_HOME（DSH 技能目录）。跳过技能安装。"
  Write-Host "  之后可用：powershell -File setup\install.ps1 -SkillsDir ""C:\Users\<你>\.dsh-packs\<profile>"""
} else {
  $targetSkills = Join-Path $SkillsDir "skills"
  New-Item -ItemType Directory -Force $targetSkills | Out-Null
  $count = 0
  Get-ChildItem (Join-Path $Root "skills") -Directory | ForEach-Object {
    $dest = Join-Path $targetSkills $_.Name
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item (Join-Path $_.FullName "SKILL.md") (Join-Path $dest "SKILL.md") -Force
    $count++
  }
  Write-Host "  已安装 $count 个技能到 $targetSkills"
}

# 5. 桌面快捷方式
Write-Host "[5/5] 创建桌面快捷方式……"
try {
  $ws = New-Object -ComObject WScript.Shell
  $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "水处理·电气自动化工作台.lnk"))
  $lnk.TargetPath = Join-Path $Root "ui\start.cmd"
  $lnk.WorkingDirectory = Join-Path $Root "ui"
  $lnk.Description = "打开水处理与电气自动化整合包工作台"
  $lnk.Save()
  Write-Host "  桌面快捷方式已创建"
} catch { Write-Host "  快捷方式创建失败（可手动双击 ui\start.cmd 启动）" }

Write-Host ""
Write-Host "=== 部署完成 ==="
Write-Host "1. 双击桌面快捷方式打开工作台；"
Write-Host "2. 在 DSH 对话中说“导入整合包自动化”，按提示完成招标监控定时任务导入；"
Write-Host "3. 可选：DSH CLI 安装可视化插件（见 plugins\插件清单.md）。"
