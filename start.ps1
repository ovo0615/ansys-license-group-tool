# Ansys License 分組設定工具 — 啟動腳本
# 此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供
$ErrorActionPreference = "Stop"

# ── UTF-8 Console 編碼設定 ──────────────────────────────────
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding  = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Ansys License 分組設定工具" -ForegroundColor Cyan
Write-Host "  此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# ── 確認 uv 已安裝 ────────────────────────────────────────
$uvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host "[錯誤] 找不到 uv 指令，請先安裝 uv：" -ForegroundColor Red
    Write-Host "       PowerShell 執行：powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"" -ForegroundColor Yellow
    Read-Host "按 Enter 結束"
    exit 1
}

# ── Python 相容性探測（3.10 ~ 3.12，64 位元）────────────────
$supportedVersions = @("3.12", "3.11", "3.10")
$venvPy = Join-Path $scriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "[1/3] 偵測可用 Python 版本（支援 3.10 ~ 3.12 64 位元）..." -ForegroundColor Yellow

    $foundPython = $null

    # 方法一：Python Launcher（py.exe）版本選擇器
    foreach ($ver in $supportedVersions) {
        try {
            & py "-$ver-64" -c "exit()" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $foundPython = "py -$ver-64"
                Write-Host "    找到：Python $ver (64 位元，透過 py.exe)" -ForegroundColor Green
                break
            }
        } catch { }
    }

    # 方法二：具名 python 命令
    if (-not $foundPython) {
        foreach ($cmd in @("python3", "python")) {
            try {
                $verOut = & $cmd --version 2>$null
                if ($LASTEXITCODE -eq 0 -and $verOut -match "Python (3\.\d+)") {
                    $detected = $Matches[1]
                    if ($supportedVersions -contains $detected) {
                        $foundPython = $cmd
                        Write-Host "    找到：Python $detected (透過 $cmd)" -ForegroundColor Green
                        break
                    }
                }
            } catch { }
        }
    }

    # 方法三：已知使用者安裝路徑
    if (-not $foundPython) {
        foreach ($ver in $supportedVersions) {
            $verNoDot = $ver -replace "\.",""
            $candidate = "$env:LOCALAPPDATA\Programs\Python\Python$verNoDot\python.exe"
            if (Test-Path $candidate) {
                try {
                    & $candidate --version 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        $foundPython = $candidate
                        Write-Host "    找到：Python $ver (使用者安裝路徑)" -ForegroundColor Green
                        break
                    }
                } catch { }
            }
        }
    }

    # 找不到相容版本 → 提示 WinGet 安裝
    if (-not $foundPython) {
        Write-Host "" 
        Write-Host "[錯誤] 找不到相容的 Python（3.10 ~ 3.12 64 位元）。" -ForegroundColor Red
        Write-Host ""
        Write-Host "  自動安裝（需要 WinGet）：" -ForegroundColor Yellow
        $winget = Get-Command "winget" -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Host "  正在嘗試透過 WinGet 安裝 Python 3.12..." -ForegroundColor Yellow
            winget install `
                --id Python.Python.3.12 `
                --exact `
                --source winget `
                --scope user `
                --architecture x64 `
                --silent `
                --accept-package-agreements `
                --accept-source-agreements `
                --disable-interactivity
            # 安裝後重新偵測
            $refreshed = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
            if (Test-Path $refreshed) {
                $foundPython = $refreshed
                Write-Host "  Python 3.12 安裝完成。" -ForegroundColor Green
            }
        }
        if (-not $foundPython) {
            Write-Host "  請手動安裝 Python 3.10 ~ 3.12（64 位元）：" -ForegroundColor Yellow
            Write-Host "  https://www.python.org/downloads/" -ForegroundColor Cyan
            Write-Host "  安裝後請重新執行 run_tool.bat" -ForegroundColor Yellow
            Read-Host "按 Enter 結束"
            exit 1
        }
    }
} else {
    Write-Host "[1/3] 已有虛擬環境，略過 Python 偵測。" -ForegroundColor Green
}

# ── 同步依賴套件 ──────────────────────────────────────────
Write-Host "[2/3] 同步依賴套件（首次執行需要網路）..." -ForegroundColor Yellow
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "[錯誤] uv sync 失敗，請確認網路連線。" -ForegroundColor Red
    Read-Host "按 Enter 結束"
    exit 1
}
Write-Host "      套件同步完成。" -ForegroundColor Green

# ── 啟動 GUI ──────────────────────────────────────────────
Write-Host "[3/3] 啟動 GUI..." -ForegroundColor Yellow
Write-Host ""
& uv run ansys_license_group_tool.py