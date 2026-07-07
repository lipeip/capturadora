@echo off
REM Ejecuta este .bat una vez para ver el nombre EXACTO de tu capturadora.
cd /d "%~dp0"
ffmpeg -hide_banner -list_devices true -f dshow -i dummy
echo.
echo ----------------------------------------------------------
echo Copia el nombre que aparece junto a (video) -por ejemplo
echo "USB Video"- y pegalo dentro de capturadora.bat.
echo ----------------------------------------------------------
pause
