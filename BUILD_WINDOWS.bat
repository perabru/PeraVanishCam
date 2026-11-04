@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Instale Python 3.11 de 64 bits antes de criar o executavel.
  goto :error
)

py -3.11 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>nul
if errorlevel 1 (
  echo Instale Python 3.11 de 64 bits com o Python Launcher antes de compilar.
  goto :error
)

py -3.11 -c "import PyInstaller, cv2, mediapipe, numpy, pyvirtualcam, pygame" >nul 2>nul
if errorlevel 1 (
  echo Instalando as dependencias de compilacao...
  py -3.11 -m pip install -r requirements-windows.txt
  if errorlevel 1 goto :error
)

if not exist "models\gesture_recognizer.task" goto :models
if not exist "models\selfie_segmenter_landscape.tflite" goto :models
goto :build

:models
echo Baixando os modelos MediaPipe necessarios...
py -3.11 -c "from vanish_cam import download_models; download_models()"
if errorlevel 1 goto :error

:build
py -3.11 -m PyInstaller --clean --noconfirm --distpath dist --workpath build PeraVanishCam.spec
if errorlevel 1 goto :error

"dist\PeraVanishCam.exe" --self-test
if errorlevel 1 goto :error

echo.
echo Pronto: dist\PeraVanishCam.exe
exit /b 0

:error
echo.
echo Falha na compilacao. Confira as mensagens acima.
pause
exit /b 1
