# Spielt addon/mealprepper auf Home Assistant aus und baut das lokale Add-on neu.
# Deinstalliert nichts — die Datenbank in /data bleibt erhalten.
#
# Erwartet in der Umgebung oder in .env im Repo-Root:
#   HA_URL    z. B. http://192.168.1.200:8123
#   HA_TOKEN  langlebiges Home-Assistant-Token (Profil → Sicherheit)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Root "addon\mealprepper"
$EnvFile = Join-Path $Root ".env"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $name, $value = $line.Split("=", 2)
        $value = $value.Trim().Trim('"').Trim("'")
        if (-not $value) { return }
        if (-not [string]::IsNullOrWhiteSpace($name) -and -not (Test-Path "Env:$name")) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

$HaUrl = ($env:HA_URL, "http://192.168.1.200:8123" | Where-Object { $_ } | Select-Object -First 1).TrimEnd("/")
$Token = $env:HA_TOKEN
$Share = if ($env:HA_ADDON_SHARE) { $env:HA_ADDON_SHARE } else { "\\homeassistant\addons\mealprepper" }
$Slug = if ($env:HA_ADDON_SLUG) { $env:HA_ADDON_SLUG } else { "local_mealprepper" }

if (-not $Token) {
    throw "HA_TOKEN fehlt. Im Home Assistant: Profil → Sicherheit → langlebiges Token, dann in .env setzen."
}
if (-not (Test-Path $Source)) {
    throw "Quellordner fehlt: $Source"
}

function Invoke-HaSupervisor([string]$Method, [string]$Path, [int]$TimeoutSec = 60) {
    $headers = @{
        Authorization = "Bearer $Token"
        "Content-Type" = "application/json"
    }
    $uri = "$HaUrl/api/hassio$Path"
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -TimeoutSec $TimeoutSec
}

Write-Host "1/4 Dateien nach $Share kopieren"
New-Item -ItemType Directory -Force -Path $Share | Out-Null

$items = Get-ChildItem -Force $Source | Where-Object { $_.Name -notin @("www", "__pycache__") }
foreach ($item in $items) {
    Copy-Item -Force -Recurse -Path $item.FullName -Destination $Share
}
$wwwShare = Join-Path $Share "www"
New-Item -ItemType Directory -Force -Path $wwwShare | Out-Null
Get-ChildItem -Force (Join-Path $Source "www") | ForEach-Object {
    Copy-Item -Force -Recurse -Path $_.FullName -Destination $wwwShare
}

Write-Host "2/4 Add-on-Liste im Supervisor neu einlesen"
Invoke-HaSupervisor POST "/store/reload" | Out-Null

$installed = $false
try {
    Invoke-HaSupervisor GET "/addons/$Slug/info" | Out-Null
    $installed = $true
} catch {
    $installed = $false
}

if ($installed) {
    Write-Host "3/4 Add-on $Slug neu bauen (Datenbank bleibt)"
    Invoke-HaSupervisor POST "/addons/$Slug/rebuild" 600 | Out-Null
} else {
    Write-Host "3/4 Add-on $Slug erstmals installieren"
    Invoke-HaSupervisor POST "/addons/$Slug/install" 600 | Out-Null
}

Write-Host "4/4 Add-on starten"
try {
    Invoke-HaSupervisor POST "/addons/$Slug/start" 120 | Out-Null
} catch {
    Write-Host "Start-Aufruf übersprungen (läuft vermutlich schon): $($_.Exception.Message)"
}

$info = Invoke-HaSupervisor GET "/addons/$Slug/info"
$state = $info.data.state
$version = $info.data.version
Write-Host "Fertig: $Slug Version $version, Zustand $state"
Write-Host "Prüfen: $HaUrl  und  https://mp.giger-straehl.ch/api/health"
