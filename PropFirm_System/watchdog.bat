@echo off
echo Starting Osiris Trading Bot Watchdog...
:loop
python main.py
echo main.py exited with error code %errorlevel%.
echo Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
