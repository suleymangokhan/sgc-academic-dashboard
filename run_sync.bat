@echo off
cd /d %~dp0
python auto_sync_dashboard.py --data dashboard_data.json --out-js dashboard_data.js --verbose
pause
