@echo off
REM Muestra los dispositivos de video y audio que ve Windows.
cd /d "%~dp0"
echo Dispositivos detectados:
echo.
ffmpeg -hide_banner -list_devices true -f dshow -i dummy
echo.
echo ----------------------------------------------------------
echo El de (video) es tu capturadora. El de (audio) "Digital
echo Audio Interface" es el sonido HDMI del Mac.
echo ----------------------------------------------------------
pause
