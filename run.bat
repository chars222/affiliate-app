@echo off
:: Cambiar al directorio del script
cd /d "%~dp0"

:: Ejecutar usando Python portable
Python\python.exe app.py

pause
