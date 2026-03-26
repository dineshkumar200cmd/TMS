@echo off
setlocal

echo 🚀 Starting Smart Traffic Management System (Windows)...

:: Start HTTP Server for frontends
echo Starting frontend file Server (Port 8000)...
start /B python -m http.server 8000

:: Start AI Engine Backend
echo Starting AI Engine Backend (Port 5000)...
start /B venv\Scripts\python smart_tms\backend\app.py

:: Start Traffic Feed Backend
echo Starting Traffic Feed Backend (Port 5001)...
start /B venv\Scripts\python venv\traffic\backend\app.py

echo ✅ All services started successfully!
echo.
echo 🔗 Access the dashboards here:
echo 1. Top-Down 3D Simulation:       http://localhost:8000/traffic_3d.html
echo 2. Traffic Video + AI signals:     http://localhost:8000/traffic_video.html
echo 3. Smart TMS Dashboard:            http://localhost:8000/smart_tms/frontend/index.html
echo 4. Traffic Feed Dashboard:         http://localhost:8000/venv/traffic/frontend/index.html
echo.
echo Close this window to stop all services (or use Task Manager to kill Python processes).
pause
