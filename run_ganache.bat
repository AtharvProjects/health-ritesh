@echo off
title SafeHealth - Ganache Blockchain Node
echo ======================================================================
echo           Starting SafeHealth Ganache Ethereum Node (Port 8545)
echo ======================================================================
cmd /c npx ganache --host 127.0.0.1 --port 8545 --mnemonic "candy maple cake sugar pudding cream honey rich smooth crumble sweet treat"
pause
