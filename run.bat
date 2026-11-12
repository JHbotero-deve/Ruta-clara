@echo off
title Ruta Clara - Servidor de Navegación y Rutas
echo ========================================================
echo   Iniciando Ruta Clara (FastAPI + Leaflet + GPS)
echo ========================================================
echo.

:: Activar virtualenv si existe
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activando entorno virtual .venv ...
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] No se encontro .venv - usando Python del sistema.
)

:: Verificar que Python esta disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    pause
    exit /b 1
)

echo.
echo El servidor se abrira en: http://127.0.0.1:8000/map
echo Presiona CTRL+C para detener el servidor en cualquier momento.
echo.
python -m uvicorn src.main:app --reload --port 8000
pause
