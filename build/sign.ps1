
# 可选代码签名：PFX / 证书存储（硬件令牌、HSM）/ 无证书跳过
param(
    [string[]]$Files,
    [switch]$Required
)
$ErrorActionPreference = "Stop"

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kits = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending
    foreach ($kit in $kits) {
        $candidate = Join-Path $kit.FullName "x64\signtool.exe"
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

$pfx = $env:SIGN_PFX_PATH
$password = $env:SIGN_PFX_PASSWORD
$certSha1 = $env:SIGN_CERT_SHA1
$certSubject = $env:SIGN_CERT_SUBJECT
$timestamp = if ($env:SIGN_TIMESTAMP_URL) { $env:SIGN_TIMESTAMP_URL } else { "https://timestamp.digicert.com" }
if ($timestamp -eq "none") { $timestamp = "" }
$tempPfx = $null
if (-not $pfx -and $env:SIGN_PFX_BASE64) {
    $tempPfx = Join-Path $env:TEMP ("sign-" + [guid]::NewGuid().ToString("N") + ".pfx")
    [IO.File]::WriteAllBytes($tempPfx, [Convert]::FromBase64String($env:SIGN_PFX_BASE64))
    $pfx = $tempPfx
}
if (-not $pfx -and -not $certSha1 -and -not $certSubject) {
    if ($Required) { throw "未配置签名证书：设置 SIGN_PFX_PATH / SIGN_PFX_BASE64 / SIGN_CERT_SHA1 / SIGN_CERT_SUBJECT" }
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
        $signArgs = @("sign", "/fd", "SHA256")
        if ($timestamp) { $signArgs += @("/td", "SHA256", "/tr", $timestamp) }
        if ($pfx) {
            $signArgs += @("/f", $pfx)
            if ($password) { $signArgs += @("/p", $password) }
        } elseif ($certSha1) {
            $signArgs += @("/sha1", $certSha1)
        } else {
            $signArgs += @("/n", $certSubject)
        }
        $signArgs += $file
        & $signtool @signArgs
        if ($LASTEXITCODE -ne 0) { throw "签名失败：$file" }
        & $signtool verify /pa /v $file
        if ($LASTEXITCODE -ne 0) { throw "签名校验失败：$file" }
    }
}
finally {
    if ($tempPfx -and (Test-Path $tempPfx)) { Remove-Item $tempPfx -Force -ErrorAction SilentlyContinue }
}
