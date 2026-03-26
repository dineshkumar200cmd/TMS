import time
import threading
import subprocess
import os
import sys
from flask import Flask, jsonify, request
from core.ai_controller import SmartTrafficController
from core.cv_processor import CVProcessor
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Global State
controller = SmartTrafficController()
cv_processor = CVProcessor(controller)

class TrafficEngine:
    def __init__(self, ai_controller):
        self.ai = ai_controller
        self.running = True
        self.current_active_road = 'North'
        self.state = 'RED'
        self.time_left = 0
        
    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        
    def _loop(self):
        while self.running:
            for road in self.ai.roads:
                # Emergency override
                if any(self.ai.emergency[r] for r in self.ai.roads):
                    emg_road = next(r for r in self.ai.roads if self.ai.emergency[r])
                    if road != emg_road: continue 

                self.current_active_road = road
                self.ai.calculate_green_times()
                green_time = self.ai.calculated_green_times[road]
                
                if green_time <= 0: continue
                
                # Active Green Cycle
                self.state = 'GREEN'
                for t in range(int(green_time), 0, -1):
                    if any(self.ai.emergency[r] for r in self.ai.roads if r != road):
                        break
                    
                    self.time_left = t
                    time.sleep(1)
                
                # Yellow clearing time
                self.state = 'YELLOW'
                self.time_left = 3
                time.sleep(3)
                
                # Red safety buffer
                self.state = 'RED'
                self.time_left = 1
                time.sleep(1)

engine = TrafficEngine(controller)
cv_processor.engine = engine
engine.start()

# Track running visualization processes so we don't open 100 windows
active_processes = {}

from flask import Response
import cv2

def gen_frames():
    while True:
        if cv_processor.running:
            snap = cv_processor.copy_stitched()
            if snap is not None:
                ret, buffer = cv2.imencode('.jpg', snap, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.03)
        else:
            time.sleep(0.1)


def gen_frames_road(road):
    """MJPEG stream for a single approach (North / South / East / West)."""
    while True:
        if cv_processor.running:
            snap = cv_processor.copy_frame(road)
            if snap is not None:
                ret, buffer = cv2.imencode('.jpg', snap, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.03)
        else:
            time.sleep(0.1)


@app.route('/api/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/video_feed/<road>')
def video_feed_road(road):
    if road not in controller.roads:
        return jsonify({"error": "unknown road"}), 404
    return Response(gen_frames_road(road), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "controller": {
            "vehicle_counts": controller.vehicle_counts,
            "calculated_green_times": controller.calculated_green_times,
            "emergency": controller.emergency,
            "cycle_time": controller.cycle_time,
        },
        "engine": {
            "active_road": engine.current_active_road,
            "state": engine.state,
            "time_left": engine.time_left
        },
        "cv_active": cv_processor.running,
        "processes": {k: (v.poll() is None) for k, v in active_processes.items()}
    })

@app.route('/api/override', methods=['POST'])
def trigger_override():
    data = request.get_json(force=True, silent=True) or {}
    road = data.get('road')
    status = data.get('status', True)
    if road in controller.roads:
        controller.emergency[road] = status
        # If toggling on, it preempts visually immediately in the next polling tick
        return jsonify({"success": True, "road": road, "emergency": status})
    return jsonify({"error": "Invalid road"}), 400

@app.route('/api/mock_traffic', methods=['POST'])
def mock_traffic():
    """Endpoint for the visual UI or sandbox to manually push traffic numbers."""
    data = request.get_json(force=True, silent=True) or {}
    road = data.get('road')
    count = data.get('count')
    if road in controller.roads and count is not None:
        controller.vehicle_counts[road] = int(count)
        return jsonify({"success": True})
    return jsonify({"error": "Invalid data"}), 400

@app.route('/api/launch/<sim_type>', methods=['POST'])
def launch_sim(sim_type):
    """Launches standalone python graphical simulations built in pygame or tkinter."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = None
    
    if sim_type == 'cv_processor':
        if not cv_processor.running:
            cv_processor.start()
        else:
            cv_processor.stop()
        return jsonify({"success": True, "cv_running": cv_processor.running})
        
    elif sim_type == '3d_isometric':
        script_path = os.path.join(base_dir, 'simulations', 'isometric_3d.py')
    elif sim_type == '2d_sandbox':
        script_path = os.path.join(base_dir, 'simulations', 'sandbox_2d.py')
    elif sim_type == 'cv_feed':
        script_path = os.path.join(base_dir, 'simulations', 'cv_feed.py')
        
    if script_path and os.path.exists(script_path):
        # Kill old if still somehow running
        if sim_type in active_processes and active_processes[sim_type].poll() is None:
            active_processes[sim_type].terminate()
            
        p = subprocess.Popen([sys.executable, script_path], cwd=os.path.join(base_dir, 'simulations'))
        active_processes[sim_type] = p
        return jsonify({"success": True, "launched": sim_type})

    return jsonify({"error": "Simulation not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
