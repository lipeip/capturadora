@echo off
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
