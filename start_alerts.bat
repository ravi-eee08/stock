@echo off
REM 1) Right-click this file > Edit, paste your NEW bot token below (keep it private)
REM 2) Save, then double-click to start the alert watcher
cd /d E:\Python\swingdesk
set TELEGRAM_TOKEN=9260609813:AAELCQ2pRIw23AOHwg7W0PMrfzZznEZvdVM
set TELEGRAM_CHAT_ID=1721589306
REM Remove the next line after testing, so alerts run only in market hours
if exist alert_state.json del alert_state.json
python alerts.py
pause