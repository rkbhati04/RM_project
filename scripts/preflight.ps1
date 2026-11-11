param(
    [Parameter(Mandatory=$true)][string]$Network,
    [string]$Interface = "Wi-Fi",
    [switch]$NoLive
)

$checks = @()
$checks += [bool](Get-Command python -ErrorAction SilentlyContinue)
$checks += [bool]($env:VIRTUAL_ENV)
$q = Get-Command q -ErrorAction SilentlyContinue
$dumpcap = Get-Command dumpcap -ErrorAction SilentlyContinue
$tshark = Get-Command tshark -ErrorAction SilentlyContinue
$checks += [bool]$q; $checks += [bool]$dumpcap; $checks += [bool]$tshark
if ($q) { Write-Output ("q: " + (& q --version 2>&1 | Select-Object -First 1)) }
$ifaceOk = $false
if ($dumpcap) { $ifaceOk = (& dumpcap -D 2>$null | Select-String -SimpleMatch $Interface) -ne $null }
$checks += $ifaceOk
$checks += -not [string]::IsNullOrWhiteSpace($Network)
$driveRoot = [System.IO.Path]::GetPathRoot((Get-Location).Path)
$drive = [System.IO.DriveInfo]::new($driveRoot)
$checks += ($drive.AvailableFreeSpace -gt 20GB)
$lock = "data\raw\capture.lock"
if (-not $NoLive -and -not (Test-Path $lock) -and $checks -notcontains $false) {
    $liveDir = "data\raw\preflight_runs\" + (Get-Date -Format "yyyyMMdd_HHmmss")
    & python src/probe_and_capture.py --iface $Interface --network $Network --workload global --limit 1 `
        --resolvers adguard --protocols doh --repeats 1 --run-dir $liveDir
    $checks += ($LASTEXITCODE -eq 0)
} elseif (-not $NoLive) { Write-Warning "Live test skipped because capture lock exists or prerequisites failed." }
if ($checks -notcontains $false) { Write-Output "GO"; exit 0 }
Write-Output "NO-GO"; exit 1
