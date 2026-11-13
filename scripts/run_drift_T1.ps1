param(
    [string]$Interface = "Wi-Fi",
    [string]$Network = "airtel",
    [string]$QPath = ""
)

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss"), $PID
$runDir = Join-Path "data\raw\drift_runs" $stamp
$lockFile = "data\raw\capture.lock"
if (Test-Path $lockFile) { throw "Capture lock exists: $lockFile" }
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType File -Force -Path $lockFile | Out-Null
$args = @("src/probe_and_capture.py", "--iface", $Interface, "--network", $Network,
    "--batch", "T1", "--run-id", "T1-$stamp", "--run-dir", $runDir,
    "--workload", "both", "--all-domains", "--resolvers", "adguard", "quad9",
    "--protocols", "doh", "doh3", "--repeats", "3", "--repeat-start", "100",
    "--shuffle-from", "100", "--resume")
if ($QPath) { $args += @("--q-path", $QPath) }
try { & python @args } finally { Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue }
