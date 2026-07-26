[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$Python = "$env:USERPROFILE\Documents\FVM_Gate3_Evidence\runtime-py312-numpy251\.venv\Scripts\python.exe",
    [string]$ExpectedMainSha = "f1b2c76827482164a12e2924bf7119a0b150e421",
    [string]$EvidenceRoot = "$env:USERPROFILE\Documents\FVM_Gate3_Evidence"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$evidenceDir = Join-Path $EvidenceRoot "stage7-gate3-windows-full-suite-$stamp"
$junit = Join-Path $evidenceDir "full-repository.xml"
$log = Join-Path $evidenceDir "full-repository.log"
$report = Join-Path $evidenceDir "full-repository-report.json"
$zip = "$evidenceDir.zip"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

Push-Location $RepoRoot
try {
    $head = (git rev-parse HEAD).Trim()
    if ($head -ne $ExpectedMainSha) {
        throw "Expected main $ExpectedMainSha but found $head"
    }
    $status = git status --porcelain=v1 --untracked-files=all
    if ($status) { throw "Working tree is not clean before execution:`n$status" }
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Isolated Python was not found: $Python"
    }

    $runtime = & $Python -c "import json,platform,CoolProp,numpy; print(json.dumps({'platform':platform.platform(),'python':platform.python_version(),'numpy':numpy.__version__,'CoolProp':CoolProp.__version__},indent=2))"
    $runtime | Set-Content -LiteralPath (Join-Path $evidenceDir "runtime.json") -Encoding UTF8
    $runtime | Write-Host

    $env:PYTHONPATH = Join-Path $RepoRoot "src"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $env:MPLBACKEND = "Agg"
    $env:ANALYSIS_SOURCE_GIT_SHA = $head

    & $Python -m compileall -q src tests
    if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed" }

    & $Python -m pytest -q --strict-markers "--junitxml=$junit" 2>&1 |
        Tee-Object -FilePath $log
    $pytestCode = $LASTEXITCODE
    Write-Host "pytest exit code: $pytestCode"

    & $Python -m liquid_gas_transient.hem_pipeline_gate3_windows_suite `
        --junit $junit `
        --output $report
    if ($LASTEXITCODE -ne 0) {
        throw "Windows full-suite result exceeded the reviewed exact-mismatch boundary"
    }

    $finalStatus = git status --porcelain=v1 --untracked-files=all
    if ($finalStatus) { throw "Working tree is dirty after execution:`n$finalStatus" }
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path $evidenceDir -DestinationPath $zip -Force
    Write-Host "Evidence ZIP: $zip"
}
