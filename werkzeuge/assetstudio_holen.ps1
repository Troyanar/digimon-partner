# Lädt AssetStudioMod (CLI, Open Source, github.com/aelurum/AssetStudioMod) in den Ordner _extern,
# speichert dessen Hilfe-Text und probiert den Export von Agumon (Modell + Animationen als FBX).
# Ändert nichts am Spiel. Aufruf: powershell -ExecutionPolicy Bypass -File assetstudio_holen.ps1
$ErrorActionPreference = "Stop"
$base = Split-Path $PSScriptRoot -Parent
$dir  = Join-Path $base "_extern\AssetStudioModCLI"
$url  = "https://github.com/aelurum/AssetStudioMod/releases/download/v0.19.0/AssetStudioModCLI_net472_win32_64.zip"

if (-not (Get-ChildItem $dir -Recurse -Filter "AssetStudioModCLI.exe" -ErrorAction SilentlyContinue)) {
  New-Item -ItemType Directory -Force $dir | Out-Null
  $zip = Join-Path $base "_extern\AssetStudioModCLI.zip"
  Write-Host "Lade AssetStudioMod v0.19.0 ..."
  Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
  Expand-Archive $zip -DestinationPath $dir -Force
  Remove-Item $zip
}
# Das ZIP enthält einen Unterordner – die .exe dort suchen
$exe = (Get-ChildItem $dir -Recurse -Filter "AssetStudioModCLI.exe" | Select-Object -First 1).FullName
Write-Host "Programm: $exe"
$ErrorActionPreference = "Continue"
& $exe --help *> (Join-Path $dir "hilfe.txt")
Write-Host "Hilfe gespeichert in $dir\hilfe.txt"

# Erster Versuch: Agumon (Modell + Animationspaket) als Animator mit allen Animationen exportieren
$in  = Join-Path $base "_spieldaten\export_in\agumon"
$out = Join-Path $base "_spieldaten\export\agumon"
if (Test-Path $in) {
  New-Item -ItemType Directory -Force $out | Out-Null
  Write-Host "Exportiere Agumon ..."
  & $exe $in -m animator -o $out --fbx-animation all --log-output both *> (Join-Path $out "protokoll.txt")
  Write-Host "Protokoll: $out\protokoll.txt"
  Get-ChildItem $out -Recurse -File | Select-Object -First 20 | ForEach-Object { Write-Host "  $($_.FullName.Replace($out, '')) ($($_.Length) Bytes)" }
}
