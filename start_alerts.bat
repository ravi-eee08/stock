@echo off
REM Store notification credentials in .env beside alerts.py; never put secrets in this file.
REM Double-click to start the alert watcher.
cd /d E:\Python\swingdesk
REM Remove the next line after testing, so alerts run only in market hours
if exist alert_state.json del alert_state.json
python alerts.py
pause
