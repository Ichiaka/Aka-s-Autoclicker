# Aka's AutoClicker — instalador
#
#   Instalar / actualizar:
#     irm https://raw.githubusercontent.com/Ichiaka/Aka-s-Autoclicker/main/install.ps1 | iex
#
#   Desinstalar:
#     & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ichiaka/Aka-s-Autoclicker/main/install.ps1))) -Uninstall
#
# Instala en %LOCALAPPDATA%\Programs\AkasAutoClicker (sin permisos de administrador),
# lo añade al arranque de Windows y crea un acceso directo en el menú Inicio.

param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'   # en PowerShell 5.1 la barra ralentiza mucho la descarga
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$AppName  = 'AkasAutoClicker'
$Url      = "https://github.com/Ichiaka/Aka-s-Autoclicker/releases/latest/download/$AppName.exe"
$Dir      = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$Exe      = Join-Path $Dir "$AppName.exe"
$RunKey   = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$Shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) "Aka's AutoClicker.lnk"

function Stop-App {
    Get-Process -Name $AppName -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}

if ($Uninstall) {
    Stop-App
    Remove-ItemProperty -Path $RunKey -Name $AppName -ErrorAction SilentlyContinue
    Remove-Item $Shortcut -Force -ErrorAction SilentlyContinue
    Remove-Item $Dir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Aka's AutoClicker desinstalado." -ForegroundColor Green
    Write-Host "(La configuracion sigue en $env:APPDATA\$AppName; borrala a mano si quieres.)"
    return
}

Write-Host "Instalando Aka's AutoClicker..." -ForegroundColor Cyan
Stop-App
New-Item -ItemType Directory -Path $Dir -Force | Out-Null

# se descarga a un temporal para no dejar un exe a medias si falla la red
$tmp = "$Exe.download"
Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
Move-Item $tmp $Exe -Force

# arranque con Windows (misma entrada que usa la casilla BOOT WITH WINDOWS)
Set-ItemProperty -Path $RunKey -Name $AppName -Value "`"$Exe`""

# acceso directo en el menú Inicio
$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($Shortcut)
$lnk.TargetPath       = $Exe
$lnk.WorkingDirectory = $Dir
$lnk.IconLocation     = "$Exe,0"
$lnk.Save()

Start-Process $Exe
Write-Host "Listo: instalado en $Dir y configurado para arrancar con Windows." -ForegroundColor Green
