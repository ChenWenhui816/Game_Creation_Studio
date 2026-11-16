# 可选代码签名：有证书才签，没有证书则保持未签名
param(
    [Parameter(Mandatory = $true)][string[]]$Files,
    [switch]$Required
)
$ErrorActionPreference = "Stop"

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kits = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending
    foreach ($kit in $kits) {
        $candidate = Join-Path $kit.FullName "x64\signtool.exe"
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

$pfx = $env:SIGN_PFX_PATH
$password = $env:SIGN_PFX_PASSWORD
$tempPfx = $null
if (-not $pfx -and $env:SIGN_PFX_BASE64) {
    $tempPfx = Join-Path $env:TEMP ("sign-" + [guid]::NewGuid().ToString("N") + ".pfx")
    [IO.File]::WriteAllBytes($tempPfx, [Convert]::FromBase64String($env:SIGN_PFX_BASE64))
    $pfx = $tempPfx
}
if (-not $pfx) {
    if ($Required) { throw "未配置签名证书：设置 SIGN_PFX_PATH 或 SIGN_PFX_BASE64" }
    Write-Warning "未配置代码签名证书，跳过签名（文件保持未签名）。"
    return
}
$signtool = Find-SignTool
if (-not $signtool) {
    if ($Required) { throw "找不到 signtool.exe，请安装 Windows SDK" }
    Write-Warning "找不到 signtool.exe，跳过签名。"
    return
}
try {
    foreach ($file in $Files) {
        if (-not (Test-Path $file)) { throw "签名文件不存在：$file" }
        Write-Host "签名 $file"
        & $signtool sign /fd SHA256 /td SHA256 /tr "http://timestamp.digicert.com" /f $pfx /p $password $file
        if ($LASTEXITCODE -ne 0) { throw "签名失败：$file" }
        & $signtool verify /pa /v $file
        if ($LASTEXITCODE -ne 0) { throw "签名校验失败：$file" }
    }
}
finally {
    if ($tempPfx -and (Test-Path $tempPfx)) { Remove-Item $tempPfx -Force -ErrorAction SilentlyContinue }
}
