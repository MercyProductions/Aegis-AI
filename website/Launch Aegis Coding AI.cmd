@echo off
REM ============================================================================
REM Aegis Coding AI Launcher
REM ============================================================================
REM This script launches the Aegis Coding AI application.
REM
REM Requirements:
REM   - Python 3.10+ with venv module
REM   - Node.js and npm (for frontend)
REM   - Ollama running with qwen2.5-coder:7b model
REM
REM Features:
REM   - Automatic virtual environment setup
REM   - Backend: FastAPI server on port 8000
REM   - Frontend: React/Vite dev server on port 5173
REM   - Runs both servers simultaneously
REM
REM The application will be available at: http://127.0.0.1:5173
REM
REM To use the Coding AI:
REM   1. Wait for the launcher to display "Aegis Coding AI is ready at..."
REM   2. Open http://127.0.0.1:5173 in your browser
REM   3. Select a workspace directory
REM   4. Choose a mode (develop, build, review, or chat)
REM   5. Type your request and apply the generated changes
REM
REM Press Ctrl+C in the PowerShell window to stop both servers
REM ============================================================================

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1"
pause
