$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskVenv = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskVenv)) {
    $taskLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($taskLauncher) { & $taskLauncher.Source -3.12 -m venv .venv }
    else {
        $taskLauncherPath = Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'
        if (-not (Test-Path -LiteralPath $taskLauncherPath)) { throw '请先安装Python 3.12及py启动器，再运行本脚本。' }
        & $taskLauncherPath -3.12 -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw '创建Python环境失败。' }
}
try {
    & $taskVenv -c 'import streamlit, plotly, sklearn, pandas' 2>$null
    $taskDepsReady = ($LASTEXITCODE -eq 0)
} catch { $taskDepsReady = $false }
if (-not $taskDepsReady) {
    Write-Host '首次运行正在安装依赖，需要网络。安装完成后，提交包内的行情支持离线演示。'
    & $taskVenv -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络后重试。' }
}
& $taskVenv -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
