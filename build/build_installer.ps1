# 构建 Inno Setup 安装包（可先签名 exe）
param([string]$Version = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not $Version) {
    $line = Get-Content scripts/version.py | Select-String 'VERSION =' | Select-Object -First 1
    $Version = $line.Line.Split('"')[1]
}
$dist = Join-Path $root "dist/Personal_Game_Studio_UE"
$exe = Join-Path $dist "Personal_Game_Studio_UE.exe"
if (-not (Test-Path $exe)) {
    throw "先构建桌面版：python -m PyInstaller --noconfirm --clean build/desktop.spec"
}
# 有证书则先签 exe，再打包安装器；安装器本身也再签一次
& (Join-Path $PSScriptRoot "sign.ps1") -Files $exe

function Find-Iscc {
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 7\ISCC.exe"
    )) { if (Test-Path $p) { return $p } }
    return $null
}
$iscc = Find-Iscc
if (-not $iscc) { throw "找不到 Inno Setup 6 的 ISCC.exe；请安装 Inno Setup 6 或 choco install innosetup" }
& $iscc "/DAppVersion=$Version" "build\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败" }
$setup = Join-Path $root "dist/Personal_Game_Studio_UE-$Version-setup.exe"
if (-not (Test-Path $setup)) { throw "安装包未生成：$setup" }
& (Join-Path $PSScriptRoot "sign.ps1") -Files $setup
Write-Host "==> 完成：$setup" -ForegroundColor Green
