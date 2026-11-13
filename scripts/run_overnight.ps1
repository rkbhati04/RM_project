param(
    [string]$Interface = "Wi-Fi",
    [string]$Network = "airtel",
    [string]$QPath = "",
    [string]$RunDir = ""
)

$runStamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss"), $PID
$runDir = if ($RunDir) { $RunDir } else { Join-Path "data\raw\overnight_runs" $runStamp }
if (-not $RunDir -and (Test-Path $runDir)) { throw "Refusing to reuse existing overnight run directory: $runDir" }
$lockFile = "data\raw\capture.lock"
if (Test-Path $lockFile) { throw "Capture lock exists: $lockFile" }
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType File -Force -Path $lockFile | Out-Null
$batch = if ($RunDir) { "T0" } else { "overnight-$runStamp" }

$arguments = @(
    "src/probe_and_capture.py", "--iface", $Interface, "--network", $Network,
    "--batch", $batch, "--run-id", $batch, "--run-dir", $runDir,
    "--workload", "both", "--all-domains", "--resolvers",
    "adguard", "cloudflare", "google", "quad9", "--protocols", "doh", "doh3",
    "--repeats", "12", "--repeat-start", "8", "--shuffle-from", "8", "--resume"
)
if ($QPath) { $arguments += @("--q-path", $QPath) }
try {
    $consecutiveFailures = 0
    $maximumFailures = 3
    while ($consecutiveFailures -lt $maximumFailures) {
        .venv\Scripts\python.exe @arguments
        if ($LASTEXITCODE -eq 0) { exit 0 }
        $consecutiveFailures++
        if ($consecutiveFailures -lt $maximumFailures) {
            Write-Warning "Capture driver failed; retrying in 60 seconds ($consecutiveFailures/$maximumFailures)."
            Start-Sleep -Seconds 60
        }
    }
    throw "Capture driver failed $maximumFailures consecutive times. Inspect the manifest before retrying."
} finally {
    Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
}
