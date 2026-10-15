param(
  [Parameter(Mandatory = $true)][int]$Port,
  [Parameter(Mandatory = $true)][string]$BaseUrl,
  [Parameter(Mandatory = $false)][string]$InstallDir
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

if (-not $isMediHisaab) {
  Write-Error "Port $Port is occupied by another service (PID: $($listener.OwningProcess)). Close that service, then start MediHisaab again."
  exit 1
}

# Check if the running daemon is stale (e.g. from an old install dir, or older than updated files on disk)
$isStale = $false

if ($InstallDir) {
  $resolvedInstall = (Resolve-Path $InstallDir -ErrorAction SilentlyContinue)
  if ($resolvedInstall -and $processInfo.ExecutablePath) {
    $procPath = (Resolve-Path $processInfo.ExecutablePath -ErrorAction SilentlyContinue)
    if ($procPath -and -not $procPath.Path.StartsWith($resolvedInstall.Path, [System.StringComparison]::OrdinalIgnoreCase)) {
      Write-Host "Running daemon is from another folder ($($procPath.Path)). Restarting with current installation."
      $isStale = $true
    }
  }

  $webIndex = Join-Path $InstallDir "web\index.html"
  if (Test-Path $webIndex) {
    $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and ((Get-Item $webIndex).LastWriteTime -gt $proc.StartTime)) {
      Write-Host "Application web assets have been updated since daemon started. Restarting daemon."
      $isStale = $true
    }
  }

  $daemonExe = Join-Path $InstallDir "daemon\pharmacy-daemon.exe"
  if (Test-Path $daemonExe) {
    $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and ((Get-Item $daemonExe).LastWriteTime -gt $proc.StartTime)) {
      Write-Host "Daemon executable has been updated since process started. Restarting daemon."
      $isStale = $true
    }
  }
}

if ($isStale) {
  Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
  exit 0
}

try {
  $page = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 3
  $isApplicationPage = $page.StatusCode -eq 200 -and
    $page.Headers["Content-Type"] -match "text/html" -and
    $page.Content -match "MediHisaab|assets/index-"
} catch {
  $isApplicationPage = $false
}

if ($isApplicationPage) {
  Write-Host "A MediHisaab app server is already running and up-to-date. Reusing it."
  exit 2
}

# Process is running but not serving the app page properly: restart it
Write-Host "Restarting unresponsive MediHisaab daemon (PID: $($listener.OwningProcess))."
Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
exit 0
