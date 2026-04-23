@echo off
:: ✈ Agentic AI Workflow for Aeroplanes - Windows Quick Start
:: Run from project root: start.bat

echo.
echo   ✈  AGENTIC AI WORKFLOW FOR AEROPLANES
echo   ══════════════════════════════════════
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
echo [OK] Python found

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Node.js found

:: Backend setup
echo.
echo [*] Setting up backend...
cd backend

if not exist "venv" (
    echo     Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo     Installing packages...
pip install -r requirements.txt -q

echo     Installing Playwright Chromium...
playwright install chromium

if not exist ".env" (
    copy .env.example .env
    echo [NOTICE] Created .env - add ANTHROPIC_API_KEY for Vision Agent
)

cd ..

:: Frontend setup
echo.
echo [*] Setting up frontend...
cd frontend

if not exist "node_modules" (
    echo     Installing npm packages...
    npm install --silent
)

cd ..

echo.
echo [OK] Setup complete!
echo.
echo [*] Starting backend on port 8000...
start "Backend" cmd /k "cd backend && venv\Scripts\activate && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [*] Starting frontend on port 5173...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo [OK] Both servers starting...
echo     Backend:  http://localhost:8000
echo     Frontend: http://localhost:5173
echo.
echo Open http://localhost:5173 in your browser
pause
