import cv2
import threading
import time

class CVProcessor:
    """Background service that reads 4 distinct video streams, detects cars, and updates the AI Controller."""

    ROAD_LABELS = {
        'North': 'North approach (roadside / top)',
        'South': 'South approach (roadside / top)',
        'East': 'East approach (roadside / top)',
        'West': 'West approach (roadside / top)',
    }
    
    def __init__(self, ai_controller, cascade_path="cars.xml"):
        import os
        import sys

        self.ai = ai_controller
        self.running = False
        self._frame_lock = threading.Lock()
        self.latest_frames = {}
        self.latest_stitched = None
        
        # Project root (same folder as road_video_config.py)
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if base not in sys.path:
            sys.path.insert(0, base)
        from road_video_config import open_all_captures

        self.cascade_path = os.path.join(base, cascade_path.split("/")[-1])
        
        # Load the Haar Cascade
        self.car_cascade = cv2.CascadeClassifier(self.cascade_path)
        
        # Four separate clips — see road_video_config.py (videos/north_road.mp4 … or fallbacks)
        self.caps, self._video_sources = open_all_captures(base)

    def copy_frame(self, road):
        """Thread-safe copy of the latest annotated frame for one road, or None."""
        with self._frame_lock:
            if road not in self.latest_frames:
                return None
            return self.latest_frames[road].copy()

    def copy_stitched(self):
        with self._frame_lock:
            if self.latest_stitched is None:
                return None
            return self.latest_stitched.copy()
            
    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self._process_loop, daemon=True).start()
        
    def stop(self):
        self.running = False

    def _process_loop(self):
        """Heavy OpenCV thread processing frames and counting cars."""
        while self.running:
            for road in self.ai.roads:
                cap = self.caps[road]
                if not cap.isOpened():
                    continue
                    
                ret, frame = cap.read()
                
                # Loop videos infinitely
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret: 
                        continue
                
                # Downsize frame for processing speed
                frame = cv2.resize(frame, (640, 360))
                
                # Mirror West approach to create a 4th unique perspective
                if road == 'West':
                    frame = cv2.flip(frame, 1) # Horizontal flip
                
                # OpenCV detection — tuned for roadside / elevated views (smaller min window helps distant cars)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                cars = self.car_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.05,
                    minNeighbors=4,
                    minSize=(18, 18),
                    flags=cv2.CASCADE_SCALE_IMAGE,
                )
                
                for (x,y,w,h) in cars:
                    cv2.rectangle(frame, (x,y), (x+w,y+h), (0, 255, 255), 2)
                label = self.ROAD_LABELS.get(road, road)
                cv2.putText(frame, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(
                    frame,
                    f"Vehicles: {len(cars)}",
                    (12, 52),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 180),
                    2,
                    cv2.LINE_AA,
                )
                
                # Draw live AI Traffic Light Overlay
                state = 'RED'
                if hasattr(self, 'engine'):
                    state = self.engine.state if self.engine.current_active_road == road else 'RED'
                    
                cv2.rectangle(frame, (580, 20), (620, 120), (30, 30, 30), -1)
                cv2.rectangle(frame, (580, 20), (620, 120), (200, 200, 200), 1)
                r_col = (0, 0, 255) if state == 'RED' else (40, 40, 40)
                y_col = (0, 255, 255) if state == 'YELLOW' else (40, 40, 40)
                g_col = (0, 255, 0) if state == 'GREEN' else (40, 40, 40)
                cv2.circle(frame, (600, 40), 12, r_col, -1)
                cv2.circle(frame, (600, 70), 12, y_col, -1)
                cv2.circle(frame, (600, 100), 12, g_col, -1)
                
                with self._frame_lock:
                    self.latest_frames[road] = frame.copy()
                
                # Update true Live Math Variables
                self.ai.vehicle_counts[road] = len(cars)
            
            with self._frame_lock:
                if len(self.latest_frames) == 4:
                    import numpy as np
                    top = np.hstack((self.latest_frames['North'], self.latest_frames['East']))
                    bottom = np.hstack((self.latest_frames['West'], self.latest_frames['South']))
                    self.latest_stitched = np.vstack((top, bottom))

            # Recalculate green times globally after polling all 4 feeds
            self.ai.calculate_green_times()
            
            # Prevent 100% CPU lock; poll ~25 FPS
            time.sleep(0.04) 
