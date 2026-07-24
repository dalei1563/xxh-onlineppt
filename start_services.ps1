$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$coreLog = Join-Path $projectRoot "server.core.log"
$coreErrorLog = Join-Path $projectRoot "server.core.error.log"
$aiLog = Join-Path $projectRoot "server.ai-voice.log"
$aiErrorLog = Join-Path $projectRoot "server.ai-voice.error.log"

function Assert-PortAvailable {
    param([int]$Port)
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        throw "端口 $Port 已被进程 $($listener.OwningProcess) 占用"
    }
}

Assert-PortAvailable 8000
Assert-PortAvailable 8100

$core = Start-Process -FilePath "python" -ArgumentList "main.py" `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput $coreLog -RedirectStandardError $coreErrorLog -PassThru

$ai = Start-Process -FilePath "python" -ArgumentList "ai_voice_service/main.py" `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput $aiLog -RedirectStandardError $aiErrorLog -PassThru

Write-Host "PPT 核心服务已启动: PID=$($core.Id), http://127.0.0.1:8000"
Write-Host "AI 语音服务已启动: PID=$($ai.Id), http://127.0.0.1:8100"
Write-Host "日志位于项目根目录的 server.core.* 和 server.ai-voice.* 文件"
