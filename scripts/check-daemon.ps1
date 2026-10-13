param(
  [Parameter(Mandatory = $true)][int]$Port,
  [Parameter(Mandatory = $true)][string]$BaseUrl
)

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
  Select-Object -First 1

if (-not $listener) {
  exit 0
}

$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
$isMediHisaab = $processInfo -and (
  $processInfo.Name -ieq "pharmacy-daemon.exe" -or
  $processInfo.CommandLine -match "pharmacy_daemon"
)

try {
  $page = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 3
  $isApplicationPage = $page.StatusCode -eq 200 -and
    $page.Headers["Content-Type"] -match "text/html" -and
    $page.Content -match "MediHisaab|assets/index-"
} catch {
  $isApplicationPage = $false
}

if ($isApplicationPage) {
  Write-Host "A MediHisaab app server is already running. Reusing it."
  exit 2
}

if ($isMediHisaab) {
  Write-Host "Restarting the older MediHisaab daemon so it serves the installed app files."
  Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
  Start-Sleep -Seconds 2
  exit 0
}

Write-Error "Port $Port is occupied by another service. Close that service, then start MediHisaab again."
exit 1
