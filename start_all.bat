@echo off
title SafeHealth - One-Click Launcher
echo ======================================================================
echo              SafeHealth Blockchain Healthcare System
echo ======================================================================

echo [1/3] Checking Ganache blockchain status...
netstat -ano | findstr 8545 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo       Ganache is already running on port 8545.
) else (
    echo       Starting Ganache in background window...
    start "SafeHealth Ganache Node" cmd /c "npx ganache --host 127.0.0.1 --port 8545 --mnemonic \"candy maple cake sugar pudding cream honey rich smooth crumble sweet treat\""
    echo       Waiting 4 seconds for Ganache to initialize...
    timeout /t 4 /nobreak >nul
)

echo [2/3] Checking deployed smart contract artifacts...
if not exist "build\contracts\HealthcareRecords.json" (
    echo       Compiling and deploying contracts...
    cmd /c npx truffle migrate --reset
) else (
    echo       Smart contracts already built and available.
)

echo [3/3] Launching SafeHealth web portal...
start http://127.0.0.1:5000/
python app_v2/run.py
pause
