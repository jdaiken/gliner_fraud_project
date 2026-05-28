@echo off
cd /d "%~dp0"
echo Starting Risk Analysis Profile dashboard...
python launch_dashboard.py
if errorlevel 1 pause
