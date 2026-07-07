@echo off
REM ============================================================
REM  Respaldo directo por si el .exe no arrancase.
REM  Reproduce la capturadora en YUYV 1080p (lo que SI funciona
REM  en esta tarjeta). Cierra ffplay previos y detecta el nombre
REM  del dispositivo automaticamente. No hay que editar nada.
REM ============================================================
cd /d "%~dp0"
setlocal enabledelayedexpansion

REM 1) Cierra cualquier ffplay colgado (adios Administrador de tareas)
taskkill /F /IM ffplay.exe >nul 2>&1

REM 2) Detecta el nombre del dispositivo de video (texto entre comillas
REM    de la linea marcada con (video) en la lista de ffmpeg)
set "DISPOSITIVO="
for /f "usebackq tokens=1 delims=" %%L in (`ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2^>^&1 ^| findstr /C:"(video)"`) do (
  if not defined DISPOSITIVO (
    set "l=%%L"
    for /f tokens^=2^ delims^=^" %%N in ("!l!") do set "DISPOSITIVO=%%N"
  )
)

if not defined DISPOSITIVO (
  echo No se detecto ninguna capturadora de video.
  echo Conecta la UGREEN, cierra Camara/Teams/Zoom y vuelve a ejecutar.
  echo.
  pause
  exit /b 1
)

echo Reproduciendo: !DISPOSITIVO!
echo   F = pantalla completa    Q = cerrar
echo.

REM 3) Reproduce en YUYV 1080p, perfil calidad
ffplay -hide_banner -loglevel warning -f dshow -pixel_format yuyv422 -video_size 1920x1080 -rtbufsize 256M -i video="!DISPOSITIVO!" -framedrop -window_title "Capturadora"

if errorlevel 1 (
  echo.
  echo -------------------------------------------------------------
  echo No se pudo reproducir. Causas mas probables:
  echo   - La capturadora esta ocupada por otra app ^(Camara, Teams...^)
  echo   - No hay fuente conectada/encendida en la entrada HDMI
  echo Cierra esas apps, revisa el cable y vuelve a ejecutar.
  echo -------------------------------------------------------------
  pause
)@echo off
REM Respaldo directo por si el .exe no arrancase. Lanza ffplay a 1080p60 MJPEG.
cd /d "%~dp0"

REM ====== PEGA AQUI el nombre EXACTO de tu capturadora, entre comillas ======
REM Para saberlo, ejecuta primero "listar.bat".
set "DISPOSITIVO=USB Video"

REM ====== AUDIO opcional (el sonido HDMI del Mac) ======
REM Pega el nombre del dispositivo (audio) que veas en listar.bat.
REM Dejalo asi -vacio- para NO capturar audio.
set "AUDIO="

if defined AUDIO (
  ffplay -hide_banner -f dshow -vcodec mjpeg -video_size 1920x1080 -framerate 60 -rtbufsize 256M -i video="%DISPOSITIVO%":audio="%AUDIO%" -framedrop -window_title "Capturadora"
) else (
  ffplay -hide_banner -f dshow -vcodec mjpeg -video_size 1920x1080 -framerate 60 -rtbufsize 256M -i video="%DISPOSITIVO%" -framedrop -window_title "Capturadora"
)

if errorlevel 1 (
  echo.
  echo No se pudo reproducir. Revisa los nombres de DISPOSITIVO / AUDIO
  echo y que ffplay.exe y ffmpeg.exe esten en esta misma carpeta.
  pause
)
