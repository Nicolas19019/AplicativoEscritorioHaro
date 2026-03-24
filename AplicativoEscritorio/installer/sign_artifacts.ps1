param(
  [Parameter(Mandatory = $true)][string]$PfxPath,
  [Parameter(Mandatory = $true)][string]$PfxPassword,
  [string]$Name = "CEA-HARO",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function Resolve-SignTool {
  $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\x64\\signtool.exe",
    "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\x86\\signtool.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }
  return $null
}

$signtool = Resolve-SignTool
if (-not $signtool) {
  Write-Host "No se encontró signtool.exe (Windows SDK)."
  Write-Host "Instala 'Windows SDK' o agrega signtool.exe al PATH."
  exit 1
}

if (-not (Test-Path $PfxPath)) {
  throw "No existe el PFX: $PfxPath"
}

$targets = @()

# EXE principal (onedir)
$appExe = Join-Path (Join-Path "dist" $Name) "$Name.exe"
if (Test-Path $appExe) { $targets += $appExe }

# EXE principal (onefile)
$appExeOne = Join-Path "dist" "$Name.exe"
if (Test-Path $appExeOne) { $targets += $appExeOne }

# Instalador(es)
$installerDir = Join-Path "dist" "installer"
if (Test-Path $installerDir) {
  $targets += (Get-ChildItem -Path $installerDir -Filter "*.exe" -File | ForEach-Object { $_.FullName })
}

$targets = $targets | Select-Object -Unique
if (-not $targets -or $targets.Count -eq 0) {
  Write-Host "No se encontraron artefactos para firmar. ¿Ya generaste el EXE/Setup?"
  exit 1
}

Write-Host "Firmando con: $signtool"
Write-Host "Archivos:"
$targets | ForEach-Object { Write-Host " - $_" }

foreach ($t in $targets) {
  & $signtool sign /fd SHA256 /f $PfxPath /p $PfxPassword /tr $TimestampUrl /td SHA256 $t | Write-Host
}

Write-Host "Firma completada."
