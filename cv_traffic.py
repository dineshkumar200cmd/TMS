import os
import cv2
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
import numpy as np

CYCLE_TIME = 120

class SmartTrafficController:
    """Core logic for calculating green times dynamically."""
    def __init__(self):
        self.roads = ['North', 'South', 'East', 'West']
        self.vehicle_counts = {'North': 0, 'South': 0, 'East': 0, 'West': 0}
        self.emergency = {'North': False, 'South': False, 'East': False, 'West': False}
        self.calculated_green_times = {'North': 30, 'South': 30, 'East': 30, 'West': 30}
        self.fixed_green_times = {'North': 30, 'South': 30, 'East': 30, 'West': 30}
        self.current_active_road = 'North'
        self.time_left = 0

    def calculate_green_times(self):
        total_vehicles = sum(self.vehicle_counts.values())
        
        for road in self.roads:
            if self.emergency[road]:
                self.calculated_green_times = {r: (30 if r == road else 0) for r in self.roads}
                return

        if total_vehicles == 0:
            self.calculated_green_times = {r: 30 for r in self.roads}
            return
            
        for road, count in self.vehicle_counts.items():
            green_time = (count / total_vehicles) * CYCLE_TIME
            if green_time < 5 and count > 0: green_time = 5
            if count == 0: green_time = 0
            self.calculated_green_times[road] = round(green_time)


class CVTrafficDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("4-Way Distinct AI Traffic Presentation")
        self.geometry("1600x1000")
        self.configure(bg="#111827")
        
        self.controller = SmartTrafficController()
        self.simulation_running = False
        
        # Four independent road clips (see road_video_config.py)
        _root = os.path.dirname(os.path.abspath(__file__))
        from road_video_config import open_all_captures
        self.caps, self._video_sources = open_all_captures(_root)
        
        self.car_cascade = cv2.CascadeClassifier('cars.xml')
        
        self.setup_ui()
        self.update_graphs_initial()
        
        self.video_running = True
        threading.Thread(target=self.cv_video_loop, daemon=True).start()

    def setup_ui(self):
        # 1. Top Control Bar
        header = tk.Frame(self, bg="#111827", pady=10)
        header.pack(fill=tk.X, padx=20)
        
        tk.Label(header, text="4-Way Smart Intersection (Independent OpenCV Feeds)", fg="white", bg="#111827", font=("Arial", 28, "bold")).pack(side=tk.LEFT)
        self.sim_btn = tk.Button(header, text="Start Signal Cycle", command=self.toggle_simulation, bg="#10b981", fg="white", font=('Arial', 14, 'bold'), padx=20)
        self.sim_btn.pack(side=tk.RIGHT)

        # 2. Main 4-Way Video Grid
        self.vid_frame = tk.Frame(self, bg="#1f2937")
        self.vid_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Grid Configuration
        self.vid_frame.columnconfigure(0, weight=1)
        self.vid_frame.columnconfigure(1, weight=1)
        self.vid_frame.rowconfigure(0, weight=1)
        self.vid_frame.rowconfigure(1, weight=1)

        self.video_labels = {}
        self.emg_vars = {}
        positions = [('North', 0, 0), ('South', 0, 1), ('East', 1, 0), ('West', 1, 1)]

        for road, r, c in positions:
            quadrant = tk.Frame(self.vid_frame, bg="#374151", bd=2, relief=tk.RAISED)
            quadrant.grid(row=r, column=c, sticky="nsew", padx=5, pady=5)
            
            # Road Header inside the video box
            top_bar = tk.Frame(quadrant, bg="#111827")
            top_bar.pack(fill=tk.X)
            tk.Label(top_bar, text=f"Road {road}", fg="#60a5fa", bg="#111827", font=("Arial", 16, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
            
            emg_var = tk.BooleanVar(value=False)
            tk.Checkbutton(top_bar, text="🚑 Emergency Override", variable=emg_var, bg="#111827", fg="#ef4444", selectcolor="black", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=10)
            self.emg_vars[road] = emg_var

            # The actual video label
            lbl = tk.Label(quadrant, bg="black")
            lbl.pack(fill=tk.BOTH, expand=True)
            self.video_labels[road] = lbl

        # 3. Bottom Analytics
        bot_frame = tk.Frame(self, bg="#111827", height=250)
        bot_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.fig, self.ax1 = plt.subplots(1, 1, figsize=(16, 2.5))
        self.fig.patch.set_facecolor('#1f2937')
        self.canvas = FigureCanvasTkAgg(self.fig, master=bot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def draw_traffic_light(self, frame, road_name):
        """Draws a Red/Green circle and the countdown timer directly onto the frame."""
        h, w, _ = frame.shape
        
        # Coordinates for Signal in Top Right
        cx, cy = w - 60, 60
        radius = 40
        
        active = (self.controller.current_active_road == road_name) and self.simulation_running
        
        color = (0, 255, 0) if active else (0, 0, 255) # BGR
        text = str(self.controller.time_left) if active else "WAIT"
        
        # Draw Background Box for contrast
        cv2.rectangle(frame, (cx - 50, cy - 50), (cx + 50, cy + 90), (0,0,0), -1)
        
        # Draw Circle
        cv2.circle(frame, (cx, cy), radius, color, -1)
        cv2.circle(frame, (cx, cy), radius, (255,255,255), 2) # border
        
        # Draw Text
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, text, (cx - 30, cy + 75), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Draw Statistics Top Left
        cv2.rectangle(frame, (10, 10), (320, 50), (0,0,0), -1)
        cv2.putText(frame, f"Detected Cars: {self.controller.vehicle_counts[road_name]}", (20, 35), font, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        
        return frame

    def cv_video_loop(self):
        """Heavy OpenCV thread processing frames, counting cars, and drawing UI Overlays for 4 inputs."""
        while self.video_running:
            ui_images = {}
            
            for road in self.controller.roads:
                cap = self.caps[road]
                ret, frame = cap.read()
                
                # Loop individual videos if they end
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret: continue # Skip if totally broken
                
                # Downsize heavy frames to keep tkinter smooth across 4 streams
                frame = cv2.resize(frame, (640, 360))
                
                # OpenCV Object Detection Pipeline
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                cars = self.car_cascade.detectMultiScale(gray, 1.1, 3)
                
                # Update true Live Math Variables per road
                self.controller.vehicle_counts[road] = len(cars)
                
                # Draw true vehicle bounding boxes
                for (x, y, w, h) in cars:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # Draw the Red/Green Traffic Light
                frame = self.draw_traffic_light(frame, road)
                
                # Convert for Tkinter
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                ui_images[road] = ImageTk.PhotoImage(image=img)

            # Push all 4 UIs dynamically to the screen in a safe thread
            self.after(0, self.render_video_frames, ui_images)
            
            # If the cycle isn't running yet, we still want the math bar chart to prove dynamic flow!
            if not self.simulation_running:
                self.after(0, self.update_environment)
                
            time.sleep(0.04)

    def render_video_frames(self, images):
        """Push rendered ImageTk objects to the Labels."""
        if not self.video_running: return
        for road in self.controller.roads:
            if road in images:
                self.video_labels[road].imgtk = images[road]
                self.video_labels[road].configure(image=images[road])

    def update_environment(self):
        for road in self.controller.roads:
            self.controller.emergency[road] = self.emg_vars[road].get()
        self.controller.calculate_green_times()
        self.update_graphs()

    def update_graphs_initial(self):
        self.update_graphs()

    def update_graphs(self):
        self.ax1.clear()
        self.ax1.set_facecolor('#1f2937')

        roads = self.controller.roads
        smart_times = [self.controller.calculated_green_times[r] for r in roads]
        fixed_times = [self.controller.fixed_green_times[r] for r in roads]

        x = np.arange(len(roads))
        width = 0.35
        
        self.ax1.bar(x - width/2, fixed_times, width, label='Fixed 30s Base', color='#9ca3af')
        self.ax1.bar(x + width/2, smart_times, width, label='Dynamic Multi-Camera Scaled Time', color='#10b981')
        
        self.ax1.set_title('Live Dynamic Green Time Distribution (Seconds)', color='white')
        self.ax1.set_xticks(x)
        self.ax1.set_xticklabels([f"{r} ({self.controller.vehicle_counts[r]} Cars)" for r in roads], color='white')
        self.ax1.tick_params(colors='white')
        
        legend = self.ax1.legend(facecolor='#111827', edgecolor='#374151')
        for text in legend.get_texts(): text.set_color("white")
        
        self.fig.tight_layout()
        self.canvas.draw()

    def toggle_simulation(self):
        if self.simulation_running:
            self.simulation_running = False
            self.sim_btn.config(text="Start Signal Cycle", bg="#10b981")
        else:
            self.simulation_running = True
            self.sim_btn.config(text="Stop Signal Cycle", bg="#ef4444")
            self.update_environment()
            threading.Thread(target=self.simulation_loop, daemon=True).start()

    def simulation_loop(self):
        while self.simulation_running:
            for road in self.controller.roads:
                if not self.simulation_running: break

                # Emergency override
                if any(self.emg_vars[r].get() for r in self.controller.roads):
                    emg_road = next(r for r in self.controller.roads if self.emg_vars[r].get())
                    if road != emg_road: continue 

                self.controller.current_active_road = road
                green_time = self.controller.calculated_green_times[road]
                
                if green_time <= 0: continue
                
                # Countdown Loop
                for t in range(int(green_time), 0, -1):
                    if not self.simulation_running: break
                    if any(self.emg_vars[r].get() for r in self.controller.roads if r != road):
                        break
                    
                    self.controller.time_left = t
                    self.after(0, self.update_environment)
                    time.sleep(1)
                
                self.controller.time_left = 0
                self.after(0, self.update_environment)

if __name__ == "__main__":
    app = CVTrafficDashboard()
    app.mainloop()
