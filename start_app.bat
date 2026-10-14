@echo off
title SafeHealth - Healthcare Record Management System
echo ======================================================================
echo           Starting SafeHealth Web Application on Port 5000
echo ======================================================================
python app_v2/run.py
if errorlevel 1 (
    echo Python execution failed. Check if Python is installed and on PATH.
    pause
)
