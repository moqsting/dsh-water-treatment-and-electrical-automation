# setup/install.ps1 —— 目标机一键部署
# 用法（在整合包根目录）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup\install.ps1
# 完成：① Python 检查（缺失可 winget 引导安装）② 离线依赖 ③ 冒烟测试
#       ④ 技能安装 ⑤ 侧边栏「工作台」按钮插件部署 ⑥ 桌面快捷方式
# 之后在 DSH 对话中说「导入整合包自动化」完成定时任务导入（见 import-into-dsh.md）。
param(
  [string]$SkillsDir = $env:DSH_HOME,   # DSH_HOME（含 skills 子目录的实例目录）
  [string]$Profile = "wet-automation",  # 侧边栏插件挂载到的 profile
  [switch]$SkipDeps
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot   # 整合包根目录

Write-Host "=== 整合包部署：water-treatment-and-electrical-automation ==="

# 1. Python 检查（缺失时可引导 winget 安装）
Write-Host "[1/6] 检查 Python 3.12 ……"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  Write-Host "  未找到 py 启动器（Python 未安装，或安装时未勾选 py launcher）。"
  $ans = Read-Host "  是否用 winget 自动安装 Python 3.12？(Y/N)"
  if ($ans -match '^[Yy]') {
    Write-Host "  正在安装 Python 3.12（可能需要几分钟）……"
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
  }
  if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "未找到 py 启动器。请安装 Python 3.12（安装时勾选 py launcher）后重试。"
  }
}
$ver = & py -3 -c "import sys; print(sys.version.split()[0])" 2>$null
if (-not $ver) { throw "py -3 不可用。请确认已安装 Python 3." }
Write-Host "  Python $ver OK"

# 2. 离线依赖（包内已内置则跳过下载，避免无谓联网）
Write-Host "[2/6] 离线依赖库（pydeps）……"
$pydeps = Join-Path $Root "pydeps"
if ($SkipDeps -or (Test-Path (Join-Path $pydeps "openpyxl"))) {
  Write-Host "  已内置（$pydeps），跳过下载。"
} else {
  Write-Host "  本地缺失，从清华镜像下载 ……"
  & py -3 (Join-Path $Root "scripts\bootstrap_libs.py")
  if ($LASTEXITCODE -ne 0) { throw "依赖安装失败，请检查网络与 pydeps 完整性。" }
}

# 3. 冒烟测试
Write-Host "[3/6] 运行整体自检（smoke_test）……"
& (Join-Path $Root "scripts\runpy.cmd") (Join-Path $Root "scripts\smoke_test.py")
if ($LASTEXITCODE -ne 0) { Write-Host "  自检未全部通过（详见输出），可继续安装；建议先排查失败项。" }

# 4. 技能安装（复制到 DSH 技能目录）
Write-Host "[4/6] 安装技能 ……"
if (-not $SkillsDir -or -not (Test-Path $SkillsDir)) {
  Write-Host "  未提供 DSH_HOME（DSH 实例目录）。跳过技能与插件安装。"
  Write-Host "  之后可用：powershell -File setup\install.ps1 -SkillsDir ""C:\Users\<你>\.dsh"""
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

# 5. 侧边栏「工作台」按钮插件部署（挂到 profile，DSH 内一键启停工作台）
Write-Host "[5/6] 部署侧边栏「工作台」按钮插件 ……"
$deploy = Join-Path $Root "setup\deploy-to-instance.py"
$pluginSrc = Join-Path $Root "plugins\open-workbench"
if ((Test-Path $deploy) -and (Test-Path $pluginSrc) -and $SkillsDir -and (Test-Path $SkillsDir)) {
  & py -3 $deploy --dsh-home $SkillsDir --profile $Profile
  if ($LASTEXITCODE -ne 0) { Write-Host "  插件部署未完成（可稍后重跑本脚本）。" }
} else {
  Write-Host "  跳过（缺少 DSH_HOME 或插件文件）。"
}

# 6. 桌面快捷方式
Write-Host "[6/6] 创建桌面快捷方式 ……"
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
Write-Host "1. DSH 侧边栏点击「工作台」按钮即可启动（或双击桌面快捷方式）；"
Write-Host "2. 在 DSH 对话中说“导入整合包自动化”，按提示完成招标监控定时任务导入；"
Write-Host "3. 首次打开工作台会弹出「选择工作区目录」，用文件资源管理器选一个你的项目目录即可。"
