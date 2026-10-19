param(
    [ValidateSet('web', 'android', 'ios', 'all')]
    [string]$Target = 'all'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'frontend'
Set-Location $frontend

function Run($cmd) {
    Write-Host ">> $cmd"
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
}

if ($Target -in @('web','all')) { Run "flutter build web" }
if ($Target -in @('android','all')) { Run "flutter build apk --debug" }
if ($Target -in @('ios','all')) {
    if ($IsMacOS) {
        Run "flutter build ios --simulator --debug"
    } else {
        Write-Host "iOS build skipped: requires macOS + Xcode (current OS is Windows). See docs/IOS_SETUP.md"
    }
}
Write-Host "Done."
