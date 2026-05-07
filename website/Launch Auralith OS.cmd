@echo off
REM ============================================================================
REM Auralith OS Launcher
REM ============================================================================
REM This script launches Auralith OS, powered by Aegis Core.
REM ============================================================================

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1"
pause
