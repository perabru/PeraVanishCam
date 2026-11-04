@echo off
setlocal
cd /d "%~dp0"
if exist "PeraVanishCam.exe" (
  "PeraVanishCam.exe" %*
  exit /b
)
if not exist ".venv-local\Scripts\python.exe" (
  echo Preparando o ambiente Python do projeto...
  where py >nul 2>nul
  if errorlevel 1 (
    python -c "import sys, struct; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8" >nul 2>nul
    if errorlevel 1 goto :python_error
    python -m venv .venv-local
  ) else (
    py -3.11 -m venv .venv-local
  )
  if errorlevel 1 goto :error
)
".venv-local\Scripts\python.exe" -c "import sys, struct; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8" >nul 2>nul
if errorlevel 1 (
  echo O ambiente .venv-local precisa de Python 3.11 de 64 bits.
  echo Renomeie a pasta .venv-local e execute este arquivo novamente.
  goto :error
)
".venv-local\Scripts\python.exe" -c "import cv2, mediapipe, numpy, pyvirtualcam, pygame" >nul 2>nul
if errorlevel 1 (
  echo Instalando as dependencias. Esta etapa precisa de internet...
  ".venv-local\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
".venv-local\Scripts\python.exe" vanish_cam.py %*
if errorlevel 1 goto :error
exit /b 0
:python_error
echo Instale Python 3.11 de 64 bits para executar o codigo-fonte.
:error
echo Nao foi possivel iniciar. Confira as instrucoes no README.md.
pause
exit /b 1
