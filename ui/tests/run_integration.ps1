# ui/tests/run_integration.ps1 —— 服务集成测试编排（受限沙箱可用：PowerShell 起 server，Node 只做 HTTP 断言）
# 用法（目标机）：pwsh -NoProfile -File ui\tests\run_integration.ps1
# 若执行策略阻止：pwsh -NoProfile -ExecutionPolicy Bypass -File ui\tests\run_integration.ps1
# 说明：Start-Process -ArgumentList 会把含空格路径截断，故用 Start-Job 参数化传递。
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ui = Join-Path $PSScriptRoot ".."
$server = Join-Path $ui "server.py"
$tmpPort = Join-Path $env:TEMP ("ui-test-" + [guid]::NewGuid().ToString("N") + ".port")

$allPass = $true
function Step($name, [scriptblock]$body) {
    Write-Host "--- $name ---"
    try { & $body; Write-Host "  OK  $name" }
    catch { Write-Host "  FAIL  $name : $($_.Exception.Message)"; $script:allPass = $false }
}

# ── 集成断言 1：端口占用时自动回退（8618 被占 → 实际端口 != 8618）──
Step "端口回退集成验证" {
    $blocker = [System.Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 8618)
    $blocker.Start()
    try {
        $job = Start-Job -ScriptBlock { param($s, $p) py -3 $s --port-file $p } -ArgumentList $server, $tmpPort
        try {
            $port = $null
            for ($i = 0; $i -lt 50; $i++) {
                if (Test-Path $tmpPort) { $port = [int](Get-Content $tmpPort -Raw).Trim(); break }
                Start-Sleep -Milliseconds 200
            }
            if ($null -eq $port) { throw "server 未启动" }
            if ($port -eq 8618) { throw "未回退（仍为 8618）" }
            Write-Host "  实际端口: $port （8618 被占，回退成功）"
        } finally {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
        }
    } finally {
        $blocker.Stop()
    }
}

# ── 集成断言 2：固定端口启动 → node:test HTTP 行为断言 ──
Step "HTTP 行为测试（node:test）" {
    $job = Start-Job -ScriptBlock { param($s) py -3 $s --port 8799 } -ArgumentList $server
    try {
        $ready = $false
        for ($i = 0; $i -lt 50; $i++) {
            try {
                $r = Invoke-WebRequest -Uri "http://127.0.0.1:8799/api/health" -TimeoutSec 2 -UseBasicParsing
                if ($r.StatusCode -eq 200) { $ready = $true; break }
            } catch { }
            Start-Sleep -Milliseconds 200
        }
        if (-not $ready) { throw "server(8799) 未就绪" }
        $env:UI_TEST_PORT = "8799"
        # 受限沙箱下 node:test runner 自身会 spawn 子进程（EPERM），故测试为纯脚本式，直接 node 运行
        node (Join-Path $PSScriptRoot "test_server.mjs")
        if ($LASTEXITCODE -ne 0) { throw "node 测试失败（exit $LASTEXITCODE）" }
    } finally {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
    }
}

Remove-Item $tmpPort -Force -ErrorAction SilentlyContinue
if ($allPass) { Write-Host "`n集成测试全部通过"; exit 0 } else { Write-Host "`n存在失败项"; exit 1 }
