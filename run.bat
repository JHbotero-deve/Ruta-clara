@echo off
title Ruta Clara - Servidor de Navegación y Rutas
echo ========================================================
echo   Iniciando Ruta Clara (FastAPI + Leaflet + GPS)
echo ========================================================
echo.
echo El servidor se abrira en: http://127.0.0.1:8000/map
echo Presiona CTRL+C para detener el servidor en cualquier momento.
echo.
python -m uvicorn src.main:app --reload --port 8000
pause


