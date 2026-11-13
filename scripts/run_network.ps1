param(
    [Parameter(Mandatory=$true)][string]$Network,
    [string]$Interface = "Wi-Fi",
    [string]$QPath = "",
    [string]$MachineLabel = "",
    [string[]]$Resolvers = @("cloudflare", "google", "adguard"),
    [string[]]$Protocols = @("doh", "doh3"),
    [int]$DomainLimit = 50,
    [int]$Repeats = 10
)

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss"), $PID
$runDir = Join-Path "data\raw\network_runs" "$Network-$stamp"
$lockFile = "data\raw\capture.lock"
$jobs = $Resolvers.Count * $Protocols.Count * ($DomainLimit * 2) * $Repeats
Write-Output ("Plan: jobs={0}, estimate={1} hours including 20% margin" -f $jobs, [math]::Round(($jobs * 3.75 * 1.2) / 3600, 1))
if (Test-Path $lockFile) { throw "Capture lock exists: $lockFile" }
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType File -Force -Path $lockFile | Out-Null
$args = @("src/probe_and_capture.py", "--iface", $Interface, "--network", $Network,
    "--batch", $Network, "--run-id", "$Network-$stamp", "--run-dir", $runDir,
    "--workload", "both", "--limit", "$DomainLimit", "--resolvers") + $Resolvers +
    @("--protocols") + $Protocols + @("--repeats", "$Repeats", "--repeat-start", "0",
    "--shuffle-from", "0", "--resume")
if ($QPath) { $args += @("--q-path", $QPath) }
if ($MachineLabel) { $args += @("--machine-label", $MachineLabel) }
try { & python @args } finally { Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue }
