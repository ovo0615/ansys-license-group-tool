# generate_release.ps1 — 產生 Release ZIP 與 SHA256SUMS.txt
# 此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供
#
# 使用方式：
#   powershell -ExecutionPolicy Bypass -File generate_release.ps1 [-Version "1.0.0"]

param(
    [string]$Version = "1.0.0"
)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$releaseName = "AnsysLicenseGroupTool_v$Version"
$releaseDir  = Join-Path $scriptDir "release_temp\$releaseName"
$zipPath     = Join-Path $scriptDir "$releaseName.zip"
$sha256Path  = Join-Path $scriptDir "SHA256SUMS.txt"

Write-Host "=== 產生 Release v$Version ===" -ForegroundColor Cyan

# 清理舊的暫存
if (Test-Path (Join-Path $scriptDir "release_temp")) {
    Remove-Item -Path (Join-Path $scriptDir "release_temp") -Recurse -Force
}
New-Item -ItemType Directory -Path $releaseDir | Out-Null

# 複製必要檔案（排除 .venv、授權敏感檔、暫存）
$includeFiles = @(
    "ansys_license_group_tool.py",
    "run_tool.bat",
    "start.ps1",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "Ansys_License_分組設定_SOP.md"
)

foreach ($file in $includeFiles) {
    $src = Join-Path $scriptDir $file
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $releaseDir $file)
        Write-Host "  + $file" -ForegroundColor Green
    } else {
        Write-Host "  ! 找不到 $file，略過" -ForegroundColor Yellow
    }
}

# 打包 ZIP
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$releaseDir\*" -DestinationPath $zipPath
Write-Host ""
Write-Host "已產生：$zipPath" -ForegroundColor Green

# 產生 SHA256
$hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash
$zipName = Split-Path $zipPath -Leaf
"$hash  $zipName" | Out-File $sha256Path -Encoding utf8 -NoNewline
Write-Host "SHA256：$hash" -ForegroundColor DarkGray
Write-Host "已產生：$sha256Path" -ForegroundColor Green

# 清理暫存
Remove-Item -Path (Join-Path $scriptDir "release_temp") -Recurse -Force

Write-Host ""
Write-Host "=== 完成 ===" -ForegroundColor Cyan
Write-Host "請在乾淨 Windows 機器上解壓 $releaseName.zip 並執行 run_tool.bat 驗證。"