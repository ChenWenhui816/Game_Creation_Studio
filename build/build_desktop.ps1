﻿# 构建 Windows 桌面版（需要 Python 3.10+）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "==> 安装构建依赖" -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-desktop.txt

Write-Host "==> PyInstaller 打包" -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm --clean build/desktop.spec

$dist = Join-Path $root "dist/Game_Creation_Studio"
if (-not (Test-Path $dist)) {
    throw "打包失败：$dist 不存在"
}
$versionLine = Get-Content scripts/version.py | Select-String 'VERSION =' | Select-Object -First 1
$version = $versionLine.Line.Split('"')[1]
$zip = Join-Path $root "dist/Game_Creation_Studio-$version.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $dist -DestinationPath $zip -CompressionLevel Optimal
Write-Host "==> 完成：$zip" -ForegroundColor Green
