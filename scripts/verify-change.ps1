#Requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Quick', 'Full')]
    [string]$Mode = 'Quick',
    [string]$PythonPath = '',
    [switch]$ShowFullOutput
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location $repo
$logDir = Join-Path $env:TEMP ("mcp-proxy-validation-" + [guid]::NewGuid().ToString('N').Substring(0, 10))
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$script:failed = 0
$script:rawBytes = 0
$script:shownBytes = 0

function Invoke-Validation {
    param([string]$Name, [scriptblock]$Command)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $outputLines = @(& $Command 2>&1 | ForEach-Object { [string]$_ })
    $code = $LASTEXITCODE
    $watch.Stop()
    $raw = ($outputLines -join "`n")
    $log = Join-Path $logDir "$Name.log"
    [IO.File]::WriteAllText($log, $raw, [Text.Encoding]::UTF8)
    $script:rawBytes += [Text.Encoding]::UTF8.GetByteCount($raw)

    $status = if ($code -eq 0) { 'PASS' } else { 'FAIL' }
    $message = "$status $Name ($([math]::Round($watch.Elapsed.TotalSeconds,2))s; exit $code)"
    if ($code -ne 0) {
        $script:failed++
        $message += "`n" + (($outputLines | Select-Object -Last 40) -join "`n")
        $message += "`nFull output: $log"
    } elseif ($ShowFullOutput -and $raw.Length -gt 0) {
        $message += "`n$raw"
    }
    $script:shownBytes += [Text.Encoding]::UTF8.GetByteCount($message)
    Write-Output $message
}

Write-Output "Repository: $repo"
Write-Output "Validation mode: $Mode; raw logs: $logDir"
Invoke-Validation 'git-diff' { git -C $repo diff --check }
Invoke-Validation 'git-staged-diff' { git -C $repo diff --cached --check }
Invoke-Validation 'ruff' { ruff check src tests }
Invoke-Validation 'ruff-format' { ruff format --check src tests }
Invoke-Validation 'pylint' { pylint --errors-only --disable=import-error src/mcp_proxy }

if ($Mode -eq 'Full') {
    if (-not $PythonPath) {
        $PythonPath = Join-Path $repo '.venv-integration/Scripts/python.exe'
    }
    if (-not (Test-Path $PythonPath)) {
        Write-Error "Isolated test Python not found: $PythonPath. Supply -PythonPath explicitly. The live .venv was not modified."
        exit 2
    }
    Invoke-Validation 'mypy' { & $PythonPath -m mypy src }
    Invoke-Validation 'pytest' { & $PythonPath -m pytest -q }
}

if ($script:rawBytes -gt 0) {
    $difference = [math]::Round(100 * (1 - $script:shownBytes / $script:rawBytes), 1)
    $label = if ($difference -ge 0) { 'estimated reduction' } else { 'small-output overhead' }
    Write-Output "Output bytes: raw=$($script:rawBytes), displayed=$($script:shownBytes), $label=$([math]::Abs($difference))%"
}
Write-Output "Results: $($script:failed) failed. Logs: $logDir"
if ($script:failed -gt 0) { exit 1 }
exit 0
