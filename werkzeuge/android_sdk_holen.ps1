# Holt die Android-Kommandozeilenwerkzeuge (Google) und Gradle, damit die Geräte-App (geraet-app/) gebaut werden kann.
# Ziel: C:\Users\<du>\Android (SDK + Gradle). Braucht ein installiertes JDK 17+ (ist da: Eclipse Adoptium).
# Aufruf: powershell -ExecutionPolicy Bypass -File werkzeuge\android_sdk_holen.ps1
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # die Fortschrittsanzeige bremst Downloads in PowerShell 5 stark aus
$root = Join-Path $env:USERPROFILE "Android"
$sdk = Join-Path $root "sdk"
$dl = Join-Path $root "downloads"
New-Item -ItemType Directory -Force $sdk, $dl | Out-Null

# 1) Android Command-line Tools
$tools = Join-Path $sdk "cmdline-tools\latest\bin\sdkmanager.bat"
if (-not (Test-Path $tools)) {
    $zip = Join-Path $dl "cmdline-tools.zip"
    Write-Host "Lade Android Command-line Tools ..."
    curl.exe -L --fail -o $zip "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    $tmp = Join-Path $dl "cmdline-tools-entpackt"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive $zip $tmp
    New-Item -ItemType Directory -Force (Join-Path $sdk "cmdline-tools") | Out-Null
    Move-Item (Join-Path $tmp "cmdline-tools") (Join-Path $sdk "cmdline-tools\latest")
}

# 2) Plattform, Build-Tools, Platform-Tools (adb) – Lizenzen werden bestätigt
$env:ANDROID_HOME = $sdk
Write-Host "Bestätige Lizenzen und installiere Plattform 35 ..."
# sdkmanager liest das "y" nicht aus einer PowerShell-Pipe, nur aus einer umgeleiteten Eingabedatei
$yes = Join-Path $dl "ja.txt"
[IO.File]::WriteAllText($yes, ("y`r`n" * 30), (New-Object System.Text.ASCIIEncoding))
Start-Process -FilePath $tools -ArgumentList "--sdk_root=$sdk", "--licenses" -RedirectStandardInput $yes -NoNewWindow -Wait
Start-Process -FilePath $tools -ArgumentList "--sdk_root=$sdk", "platform-tools", "platforms;android-35", "build-tools;35.0.0" `
    -RedirectStandardInput $yes -NoNewWindow -Wait

# 3) Gradle
$gradle = Join-Path $root "gradle-8.10.2\bin\gradle.bat"
if (-not (Test-Path $gradle)) {
    $zip = Join-Path $dl "gradle.zip"
    Write-Host "Lade Gradle 8.10.2 ..."
    curl.exe -L --fail -o $zip "https://services.gradle.org/distributions/gradle-8.10.2-bin.zip"
    Expand-Archive $zip $root -Force
}

[Environment]::SetEnvironmentVariable("ANDROID_HOME", $sdk, "User")
Write-Host ""
Write-Host "Fertig. SDK: $sdk"
Write-Host "Gradle: $gradle"
