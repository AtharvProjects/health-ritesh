@echo off
title SafeHealth - Smart Contract Deployment
echo ======================================================================
echo           Deploying HealthcareRecords Smart Contracts to Ganache
echo ======================================================================
cmd /c npx truffle migrate --reset
pause
