#!/bin/bash
# run.sh - Startup script for the Smart Traffic Management System

echo "🚀 Starting Smart Traffic Management System..."

# Start HTTP Server for frontends
echo "Starting frontend file Server (Port 8000)..."
python3 -m http.server 8000 > /dev/null 2>&1 &
HTTP_PID=$!

# Start AI Engine Backend
echo "Starting AI Engine Backend (Port 5000)..."
source venv/bin/activate
python smart_tms/backend/app.py > /dev/null 2>&1 &
AI_PID=$!

# Start Traffic Feed Backend
echo "Starting Traffic Feed Backend (Port 5001)..."
python traffic_component/backend/app.py > /dev/null 2>&1 &
FEED_PID=$!

echo "✅ All services started successfully!"
echo ""
echo "🔗 Access the dashboards here:"
echo "1. Top-Down 3D Simulation:       http://localhost:8000/traffic_3d.html"
echo "2. Traffic Video + AI signals:     http://localhost:8000/traffic_video.html"
echo "3. Smart TMS Dashboard:            http://localhost:8000/smart_tms/frontend/index.html"
echo "4. Traffic Feed Dashboard:         http://localhost:8000/traffic_component/frontend/index.html"
echo ""
echo "Press Ctrl+C to stop all services."

# Wait for user interrupt to kill background processes
trap "echo 'Terminating services...'; kill $HTTP_PID $AI_PID $FEED_PID; exit" INT
wait
