@echo off
echo ============================================
echo Group Message Scheduler - Starting All Services
echo ============================================

:: Start Main Bot
echo Starting Main Bot...
start "Main Bot" cmd /k "python -m main_bot.bot"

:: Wait a moment
timeout /t 2 /nobreak > nul

:: Start Login Bot
echo Starting Login Bot...
start "Login Bot" cmd /k "python -m login_bot.bot"

:: Wait a moment
timeout /t 2 /nobreak > nul

:: Start Worker
echo Starting Worker Service...
start "Worker" cmd /k "python -m worker.worker"

echo.
echo All services started!
echo Check the individual windows for logs.
echo.
pause
