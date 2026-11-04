@echo off
setlocal
cd /d "%~dp0"
if exist "PeraVanishCam.exe" (
  "PeraVanishCam.exe" --teste-som %*
) else (
  call INICIAR.bat --teste-som %*
)
echo.
pause
