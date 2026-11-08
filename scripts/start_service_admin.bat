@echo off
chcp 936 >nul
title Game Orchestrator - Start Elevated
cd /d "%~dp0"
echo ============================================
echo  Game Orchestrator - Start Service Elevated
echo  (This window needs Administrator rights)
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_service_admin.ps1"
echo.
pause
