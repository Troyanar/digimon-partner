# Baut die Geräte-App (APK) für ein eigenes Android-Handy.
#   powershell -ExecutionPolicy Bypass -File geraet-app\bauen.ps1                       -> für die Adresse aus geraet-app\url.txt
#   powershell -ExecutionPolicy Bypass -File geraet-app\bauen.ps1 -Url http://192.168.x.x:8420   -> Test gegen den PC im WLAN
# Ergebnis: geraet-app\DigimonPartner.apk (aufs Handy kopieren und installieren; "Unbekannte Apps installieren" erlauben)
# Vorher einmal: werkzeuge\android_sdk_holen.ps1
param([string]$Url = "")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
# Öffentliche Adresse steht in url.txt (nicht im Repo), z. B. https://partner.example.com
$urlFile = Join-Path $here "url.txt"
if (-not $Url -and (Test-Path $urlFile)) { $Url = (Get-Content $urlFile -TotalCount 1).Trim() }
if (-not $Url) { throw "Keine Adresse – -Url angeben oder geraet-app\url.txt anlegen." }
$root = Join-Path $env:USERPROFILE "Android"
$sdk = Join-Path $root "sdk"
$gradle = Join-Path $root "gradle-8.10.2\bin\gradle.bat"
if (-not (Test-Path $gradle)) { throw "Gradle fehlt – erst werkzeuge\android_sdk_holen.ps1 ausführen." }

$env:ANDROID_HOME = $sdk
Set-Content -Path (Join-Path $here "local.properties") -Value ("sdk.dir=" + ($sdk -replace '\\', '\\')) -Encoding ascii
Push-Location $here
try {
    & $gradle --no-daemon -q assembleDebug "-PpartnerUrl=$Url"
    if ($LASTEXITCODE -ne 0) { throw "Bauen fehlgeschlagen." }
} finally { Pop-Location }
$apk = Join-Path $here "app\build\outputs\apk\debug\app-debug.apk"
Copy-Item $apk (Join-Path $here "DigimonPartner.apk") -Force
# Auch zum Herunterladen über die Seite (Mehr -> Digimon-Gerät), nur für die Server-Fassung
if ($Url -like "https://*") {
    $dl = Join-Path (Split-Path -Parent $here) "data\app"
    New-Item -ItemType Directory -Force $dl | Out-Null
    Copy-Item $apk (Join-Path $dl "DigimonPartner.apk") -Force
}
Write-Host "Fertig: $(Join-Path $here 'DigimonPartner.apk')  (Adresse: $Url)"
