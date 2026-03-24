param(
  [string]$Name = "CEA-HARO",
  [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

Write-Host "==> Build EXE (PyInstaller onedir)"
Write-Host "(Recomendado para instalador: onedir, reduce falsos positivos)"
& "$PSScriptRoot\\..\\build_exe.ps1" -Name $Name -Mode "onedir" -Version $Version

function Resolve-Iscc {
  if ($env:INNO_SETUP_ISCC -and (Test-Path $env:INNO_SETUP_ISCC)) { return $env:INNO_SETUP_ISCC }

  $cmd = Get-Command iscc -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
    "C:\\Program Files\\Inno Setup 6\\ISCC.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }

  # Buscar por registro (instalación en ruta personalizada)
  $uninstallRoots = @(
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
    "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
    "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
  )
  foreach ($root in $uninstallRoots) {
    try {
      foreach ($k in (Get-ChildItem -Path $root -ErrorAction SilentlyContinue)) {
        $p = $null
        try { $p = Get-ItemProperty -Path $k.PSPath -ErrorAction SilentlyContinue } catch {}
        if (-not $p) { continue }
        $dn = [string]($p.DisplayName ?? "")
        if ($dn -notmatch "Inno Setup") { continue }

        $loc = [string]($p.InstallLocation ?? "")
        if ($loc -and (Test-Path $loc)) {
          $iscc1 = Join-Path $loc "ISCC.exe"
          if (Test-Path $iscc1) { return $iscc1 }
        }

        $icon = [string]($p.DisplayIcon ?? "")
        if ($icon) {
          # Suele traer: "...\Compil32.exe,0"
          $icon2 = $icon.Trim('"')
          $icon2 = $icon2.Split(",")[0]
          try {
            $dir = Split-Path -Parent $icon2
            if ($dir) {
              $iscc2 = Join-Path $dir "ISCC.exe"
              if (Test-Path $iscc2) { return $iscc2 }
            }
          } catch {}
        }
      }
    } catch {}
  }
  return $null
}

$iscc = Resolve-Iscc
if (-not $iscc) {
  Write-Host ""
  Write-Host "No se encontró Inno Setup Compiler (ISCC)."
  Write-Host "Instala Inno Setup 6 y vuelve a ejecutar este script."
  Write-Host "Opcional: configura la variable de entorno INNO_SETUP_ISCC con la ruta a ISCC.exe."
  exit 1
}

Write-Host "==> Build instalador (Inno Setup)"
$iss = Join-Path $PSScriptRoot "CEA-HARO.iss"
& $iscc "/DMyAppVersion=$Version" "/DMyDistDirName=$Name" "/DMyAppExeName=$Name.exe" $iss | Write-Host

Write-Host ""
Write-Host "Listo."
Write-Host "Instalador en: dist\\installer"
