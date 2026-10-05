# ui/tests/render_check.ps1 —— UI 无头渲染验证（需完整权限运行）
# 用法（需完整权限，因为受限沙箱拦截浏览器 spawn）：
#   pwsh -NoProfile -File ui\tests\render_check.ps1
# 说明：起 server（后台 job）→ Chrome headless 导出渲染后 DOM + 截图 → 断言关键内容 → 清理。
# 比 wincu+OCR 快且省 token；一次授权即可完成全部 UI 渲染验证。
param(
  [int]$Port = 8797,
  [string]$CheckUrl = "http://127.0.0.1:8797"
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ui = Join-Path $PSScriptRoot ".."
$outDir = Join-Path $PSScriptRoot "..\reports\ui-render"
New-Item -ItemType Directory -Force $outDir | Out-Null

$allPass = $true
function Check($name, [bool]$cond) {
  if ($cond) { Write-Host "  OK  $name" } else { Write-Host "  MISSING  $name"; $script:allPass = $false }
}

$job = Start-Job -ScriptBlock { param($s, $p) py -3 $s --port $p } -ArgumentList (Join-Path $ui "server.py"), $Port
try {
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { $ready = $true; break } } catch { }
    Start-Sleep -Milliseconds 200
  }
  if (-not $ready) { throw "server 未就绪" }

  $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
  if (-not (Test-Path $chrome)) { $chrome = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" }

  $domFile = Join-Path $outDir "render-dom.html"
  $shotFile = Join-Path $outDir "render-shot.png"
  & $chrome --headless=new --disable-gpu --no-sandbox --virtual-time-budget=10000 --dump-dom $CheckUrl 2>$null | Out-File -FilePath $domFile -Encoding utf8
  & $chrome --headless=new --disable-gpu --no-sandbox --virtual-time-budget=10000 --window-size=1400,900 "--screenshot=$shotFile" $CheckUrl 2>$null

  $dom = Get-Content $domFile -Raw -Encoding UTF8
  Write-Host "DOM bytes: $($dom.Length) ｜ 截图: $((Get-Item $shotFile).Length) bytes → $outDir"
  Check "页面标题(整合包工作台)" $dom.Contains("整合包工作台")
  Check "文件区显示(JS 填充)" $dom.Contains("D:\DeepSeek Harness")
  Check "环境状态 Python 3.12.4" $dom.Contains("Python 3.12.4")
  Check "环境状态 依赖库正常" $dom.Contains("依赖库正常")
  Check "环境状态 技能数" $dom.Contains("技能")
  Check "常用功能卡(报价清单处理)" $dom.Contains("报价清单处理")
  Check "快捷目录(9 项)" (([regex]::Matches($dom, 'class="dir-item"')).Count -eq 9)
  Check "环境状态 chips(4 个)" (([regex]::Matches($dom, 'status-chip')).Count -eq 4)
  Check "打开文件区按钮" $dom.Contains("打开文件区")

  # 工具页（Phase 4：8 个工具表单动态渲染）
  $toolsDomFile = Join-Path $outDir "render-tools-dom.html"
  & $chrome --headless=new --disable-gpu --no-sandbox --virtual-time-budget=10000 --dump-dom "$CheckUrl/#tools" 2>$null | Out-File -FilePath $toolsDomFile -Encoding utf8
  $toolsDom = Get-Content $toolsDomFile -Raw -Encoding UTF8
  Check "工具表单(8 个)" (([regex]::Matches($toolsDom, 'class="card tool-card"')).Count -eq 8)
  foreach ($t in @("招标清单规整", "供应商报价比对", "成本测算", "清单差异核对", "图纸清单提取", "CAD 环境检查", "整体自检", "重建依赖库")) {
    Check "工具: $t" $toolsDom.Contains($t)
  }
  Check "cost 参数表单(税率)" $toolsDom.Contains("税率 %")
  Check "diff 双文件表单(投标清单)" $toolsDom.Contains("投标清单")
} finally {
  Stop-Job $job -ErrorAction SilentlyContinue
  Remove-Job $job -Force -ErrorAction SilentlyContinue
}
if ($allPass) { Write-Host "`n渲染验证全部通过"; exit 0 } else { Write-Host "`n存在失败项"; exit 1 }
