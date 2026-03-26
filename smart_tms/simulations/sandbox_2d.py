import tkinter as tk
from tkinter import ttk
import random
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
import requests

CYCLE_TIME = 120
FPS = 60
SIMULATION_SPEED = 1.0  # Multiplier for physics speed

class SmartTrafficController:
    """Fetches AI data directly from the unified Flask backend API."""
    def __init__(self):
        self.roads = ['North', 'South', 'East', 'West']
        self.waiting_counts = {'North': 0, 'South': 0, 'East': 0, 'West': 0}
        self.emergency = {'North': False, 'South': False, 'East': False, 'West': False}
        self.calculated_green_times = {'North': 30, 'South': 30, 'East': 30, 'West': 30}
        self.current_active_road = 'North'
        self.time_left = 30
        self.state = 'RED'
        self.api_url = "http://127.0.0.1:5000/api"

    def fetch_api_state(self):
        """Poll the central server and detect new emergencies."""
        new_emergencies = []
        try:
            resp = requests.get(f"{self.api_url}/status", timeout=0.5).json()
            latest_emg = resp['controller']['emergency']
            
            for r in self.roads:
                if latest_emg[r] and not self.emergency[r]:
                    new_emergencies.append(r)
            
            self.calculated_green_times = resp['controller']['calculated_green_times']
            self.emergency = latest_emg
            self.current_active_road = resp['engine']['active_road']
            self.state = resp['engine']['state']
            self.time_left = resp['engine']['time_left']
        except:
            pass
        return new_emergencies
            
    def push_mock_data(self, road, count):
        """Pushes sandbox spawned vehicles to the global API."""
        try:
            requests.post(f"{self.api_url}/mock_traffic", json={"road": road, "count": count}, timeout=0.1)
        except:
            pass

    def calculate_green_times(self):
        self.fetch_api_state()


class Vehicle:
    """Physics class for rendering and moving a 2D car on the Canvas."""
    def __init__(self, canvas, _id, road_origin, is_emergency=False):
        self.canvas = canvas
        self.id = _id
        self.road_origin = road_origin
        self.is_emergency = is_emergency
        
        self.width, self.length = 20, 40
        self.speed = 0.0
        self.max_speed = 4.0 if not is_emergency else 6.0
        self.acceleration = 0.2
        self.braking = 0.4
        
        # Colors
        self.color = "red" if is_emergency else random.choice(["blue", "yellow", "cyan", "white", "orange", "purple"])
        
        # Intersection stop lines (approximate distances from center 400x400)
        self.stop_line_dist = 60
        self.crossed_intersection = False
        
        # Spawn logic (Lane setup for a 800x800 canvas)
        if road_origin == 'North': # Driving South
            self.x, self.y = 425, -50
            self.vx, self.vy = 0, 1
            self.length, self.width = 40, 20
            self.stop_y = 400 - self.stop_line_dist
        elif road_origin == 'South': # Driving North
            self.x, self.y = 375, 850
            self.vx, self.vy = 0, -1
            self.length, self.width = 40, 20
            self.stop_y = 400 + self.stop_line_dist
        elif road_origin == 'East': # Driving West
            self.x, self.y = 850, 425
            self.vx, self.vy = -1, 0
            self.length, self.width = 20, 40
            self.stop_x = 400 + self.stop_line_dist
        elif road_origin == 'West': # Driving East
            self.x, self.y = -50, 375
            self.vx, self.vy = 1, 0
            self.length, self.width = 20, 40
            self.stop_x = 400 - self.stop_line_dist

        # Draw to canvas
        self.rect = self.canvas.create_rectangle(
            self.x - self.width/2, self.y - self.length/2,
            self.x + self.width/2, self.y + self.length/2,
            fill=self.color, outline="black"
        )
        
        if self.is_emergency:
            # Draw flashing beacon
            self.beacon = self.canvas.create_oval(
                self.x - 5, self.y - 5, self.x + 5, self.y + 5, fill="white"
            )

    def is_waiting(self):
        """Returns True if the car is stopped at the red light."""
        if self.crossed_intersection: return False
        return self.speed < 0.5

    def get_front_coord(self):
        """Get the absolute leading edge of the car for collision detection."""
        if self.road_origin == 'North': return self.y + self.length/2
        if self.road_origin == 'South': return self.y - self.length/2
        if self.road_origin == 'East': return self.x - self.length/2
        if self.road_origin == 'West': return self.x + self.length/2

    def get_rear_coord(self):
        """Get the absolute trailing edge of the car."""
        if self.road_origin == 'North': return self.y - self.length/2
        if self.road_origin == 'South': return self.y + self.length/2
        if self.road_origin == 'East': return self.x + self.length/2
        if self.road_origin == 'West': return self.x - self.length/2

    def update(self, light_color, car_ahead):
        """Physics step: accelerate, brake, or cruise based on light and traffic."""
        target_speed = self.max_speed
        
        # 1. Traffic Light Logic (Stop Line Detection)
        dist_to_stop = 0
        at_stop_line = False
        
        if not self.crossed_intersection:
            if self.road_origin == 'North':
                dist_to_stop = self.stop_y - self.get_front_coord()
            elif self.road_origin == 'South':
                dist_to_stop = self.get_front_coord() - self.stop_y
            elif self.road_origin == 'East':
                dist_to_stop = self.get_front_coord() - self.stop_x
            elif self.road_origin == 'West':
                dist_to_stop = self.stop_x - self.get_front_coord()
                
            # If approaching the stop line and light is NOT green, prepare to stop
            if dist_to_stop > 0 and dist_to_stop < 150:
                if light_color != 'GREEN':
                    # Decelerate to stop exactly at line
                    target_speed = max(0, dist_to_stop * 0.05)
            
            # Did we cross the intersection?
            if dist_to_stop < -50:
                self.crossed_intersection = True

        # 2. Collision Avoidance (Car Ahead Logic)
        if car_ahead:
            dist_to_car = 0
            if self.road_origin == 'North':
                dist_to_car = car_ahead.get_rear_coord() - self.get_front_coord()
            elif self.road_origin == 'South':
                dist_to_car = self.get_front_coord() - car_ahead.get_rear_coord()
            elif self.road_origin == 'East':
                dist_to_car = self.get_front_coord() - car_ahead.get_rear_coord()
            elif self.road_origin == 'West':
                dist_to_car = car_ahead.get_rear_coord() - self.get_front_coord()
                
            if dist_to_car > 0 and dist_to_car < 60:
                # Brake for the car ahead
                target_speed = min(target_speed, max(0, (dist_to_car - 20) * 0.1))
                if dist_to_car < 25:
                    target_speed = 0

        # Apply Physics
        if self.speed < target_speed:
            self.speed = min(self.speed + self.acceleration, target_speed)
        elif self.speed > target_speed:
            self.speed = max(self.speed - self.braking, target_speed)

        self.x += self.vx * self.speed * SIMULATION_SPEED
        self.y += self.vy * self.speed * SIMULATION_SPEED
        
        # Redraw
        self.canvas.coords(
            self.rect,
            self.x - self.width/2, self.y - self.length/2,
            self.x + self.width/2, self.y + self.length/2
        )
        if self.is_emergency:
            # Flashing effect
            flash_color = "white" if int(time.time() * 5) % 2 == 0 else "blue"
            self.canvas.itemconfig(self.beacon, fill=flash_color)
            self.canvas.coords(
                self.beacon, self.x - 5, self.y - 5, self.x + 5, self.y + 5
            )

    def is_off_screen(self):
        return self.x < -100 or self.x > 900 or self.y < -100 or self.y > 900


class GameTrafficDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Interactive 2D Traffic Simulation")
        self.geometry("1400x900")
        self.configure(bg="#111827")
        
        self.controller = SmartTrafficController()
        self.vehicles = []
        self.vehicle_id_counter = 0
        
        self.simulation_running = False
        
        self.setup_ui()
        self.setup_intersection()
        self.update_graphs_initial()
        
        self.game_running = True
        threading.Thread(target=self.physics_loop, daemon=True).start()
        # The backend now handles the traffic light loop asynchronously, we just poll it.

    def setup_ui(self):
        # 1. Left Controls Panel
        controls = tk.Frame(self, bg="#1f2937", width=300, padx=20, pady=20)
        controls.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(controls, text="Traffic Sandbox Control", fg="white", bg="#1f2937", font=("Arial", 18, "bold")).pack(pady=(0, 20))
        
        self.sim_btn = tk.Button(controls, text="Start Signal Cycle", command=self.toggle_simulation, bg="#10b981", fg="white", font=('Arial', 14, 'bold'), pady=10)
        self.sim_btn.pack(fill=tk.X, pady=10)
        
        tk.Frame(controls, height=2, bg="#374151").pack(fill=tk.X, pady=20)
        
        # Spawning Controls
        tk.Label(controls, text="🚦 Spawn Traffic Manual", fg="#9ca3af", bg="#1f2937", font=("Arial", 12)).pack()
        
        for road in self.controller.roads:
            row = tk.Frame(controls, bg="#1f2937")
            row.pack(fill=tk.X, pady=5)
            tk.Button(row, text=f"+ Spawn {road}", command=lambda r=road: self.spawn_vehicle(r), bg="#374151", fg="white").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            tk.Button(row, text=f"+5 Burst", command=lambda r=road: self.spawn_burst(r), bg="#4b5563", fg="white").pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=2)

        tk.Frame(controls, height=2, bg="#374151").pack(fill=tk.X, pady=20)

        # Emergency
        tk.Label(controls, text="🚑 Emergency Vehicles", fg="#ef4444", bg="#1f2937", font=("Arial", 12, "bold")).pack()
        for road in self.controller.roads:
            tk.Button(controls, text=f"Send Ambulance {road}", command=lambda r=road: self.spawn_emergency(r), bg="#7f1d1d", fg="white").pack(fill=tk.X, pady=5)

        # Bot Analytics embedded in left panel
        bot_frame = tk.Frame(controls, bg="#1f2937")
        bot_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=20)
        
        self.fig, self.ax1 = plt.subplots(1, 1, figsize=(3, 3))
        self.fig.patch.set_facecolor('#1f2937')
        self.canvas_graph = FigureCanvasTkAgg(self.fig, master=bot_frame)
        self.canvas_graph.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 2. Main Game Canvas (800x800)
        self.game_container = tk.Frame(self, bg="#111827", padx=20, pady=20)
        self.game_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.game_container, width=800, height=800, bg="#2ca02c", highlightthickness=0)
        self.canvas.pack(anchor=tk.CENTER)
        
    def setup_intersection(self):
        """Draws the asphalt roads and stop lines on the Canvas."""
        w, h = 800, 800
        # Grass background is set in Canvas create. Draw Roads:
        self.canvas.create_rectangle(w/2 - 50, 0, w/2 + 50, h, fill="#3f3f3f", outline="") # N-S
        self.canvas.create_rectangle(0, h/2 - 50, w, h/2 + 50, fill="#3f3f3f", outline="") # E-W
        
        # Center Intersection Square (slight dark overlay)
        self.canvas.create_rectangle(w/2 - 50, h/2 - 50, w/2 + 50, h/2 + 50, fill="#333333", outline="")
        
        # Draw Stop Lines
        stop_offset = 60
        # North Lane Stop Line (cars heading South)
        self.canvas.create_line(w/2 + 5, h/2 - stop_offset, w/2 + 50, h/2 - stop_offset, fill="white", width=4)
        # South Lane Stop Line
        self.canvas.create_line(w/2 - 50, h/2 + stop_offset, w/2 - 5, h/2 + stop_offset, fill="white", width=4)
        # East Lane Stop Line
        self.canvas.create_line(w/2 + stop_offset, h/2 + 5, w/2 + stop_offset, h/2 + 50, fill="white", width=4)
        # West Lane Stop Line
        self.canvas.create_line(w/2 - stop_offset, h/2 - 50, w/2 - stop_offset, h/2 - 5, fill="white", width=4)

        # Dashed Lane Dividers
        for y in range(0, int(h/2 - stop_offset), 40):
            self.canvas.create_line(w/2, y, w/2, y+20, fill="yellow", width=2)
            self.canvas.create_line(w/2, h - y, w/2, h - y - 20, fill="yellow", width=2)
        for x in range(0, int(w/2 - stop_offset), 40):
            self.canvas.create_line(x, h/2, x+20, h/2, fill="yellow", width=2)
            self.canvas.create_line(w - x, h/2, w - x - 20, h/2, fill="yellow", width=2)

        # Traffic Light Indicators (Graphical Overlays near the intersections)
        self.ui_lights = {}
        r = 15
        self.ui_lights['North'] = self.canvas.create_oval(w/2 - 40, h/2 - 90, w/2 - 40 + r*2, h/2 - 90 + r*2, fill="red")
        self.ui_lights['South'] = self.canvas.create_oval(w/2 + 10, h/2 + 60, w/2 + 10 + r*2, h/2 + 60 + r*2, fill="red")
        self.ui_lights['East']  = self.canvas.create_oval(w/2 + 60, h/2 - 40, w/2 + 60 + r*2, h/2 - 40 + r*2, fill="red")
        self.ui_lights['West']  = self.canvas.create_oval(w/2 - 90, h/2 + 10, w/2 - 90 + r*2, h/2 + 10 + r*2, fill="red")
        
        # Dynamic Text overlays
        self.ui_texts = {}
        self.ui_texts['North'] = self.canvas.create_text(w/2 - 25, h/2 - 110, text="North: 0 Cars", fill="white", font=("Arial", 12, "bold"))
        self.ui_texts['South'] = self.canvas.create_text(w/2 + 25, h/2 + 110, text="South: 0 Cars", fill="white", font=("Arial", 12, "bold"))
        self.ui_texts['East']  = self.canvas.create_text(w/2 + 130, h/2 - 25, text="East: 0 Cars", fill="white", font=("Arial", 12, "bold"))
        self.ui_texts['West']  = self.canvas.create_text(w/2 - 130, h/2 + 25, text="West: 0 Cars", fill="white", font=("Arial", 12, "bold"))
        
        self.center_timer = self.canvas.create_text(w/2, h/2, text="-", fill="white", font=("Arial", 28, "bold"))

    def spawn_vehicle(self, road, is_emergency=False):
        """Creates a new vehicle and pushes it into the road array."""
        v = Vehicle(self.canvas, self.vehicle_id_counter, road, is_emergency)
        self.vehicles.append(v)
        self.vehicle_id_counter += 1
        
        if is_emergency:
            self.controller.emergency[road] = True

    def spawn_burst(self, road):
        """Spawn 5 consecutive vehicles separated by slight distance visually."""
        # Using simple threading to stagger spawns
        def burst():
            for _ in range(5):
                self.after(0, lambda: self.spawn_vehicle(road))
                time.sleep(1)
        threading.Thread(target=burst, daemon=True).start()

    def spawn_emergency(self, road, push_api=True):
        self.spawn_vehicle(road, is_emergency=True)
        # Tell the global backend immediately
        if push_api:
            try:
                requests.post(f"http://127.0.0.1:5000/api/override", 
                              json={"road": road, "status": True}, timeout=0.5)
            except: pass

    def physics_loop(self):
        """60 FPS Game Loop updating all Vehicles positions."""
        while self.game_running:
            # 1. Separate cars by road to calculate collision logic easier
            road_cars = {r: [] for r in self.controller.roads}
            for v in self.vehicles:
                road_cars[v.road_origin].append(v)
            
            # Sort cars on each road by how close they are to the intersection (to find the car "ahead")
            # Frontmost cars first
            road_cars['North'].sort(key=lambda v: v.y, reverse=True)
            road_cars['South'].sort(key=lambda v: v.y)
            road_cars['East'].sort(key=lambda v: v.x)
            road_cars['West'].sort(key=lambda v: v.x, reverse=True)

            active_road = self.controller.current_active_road

            # 2. Update Physics
            for v in self.vehicles:
                # Find car ahead of this one
                idx = road_cars[v.road_origin].index(v)
                car_ahead = road_cars[v.road_origin][idx-1] if idx > 0 else None
                
                # Determine its specific traffic light
                if not self.simulation_running:
                    light = 'RED'
                elif v.road_origin == active_road:
                    light = self.controller.state # GREEN, YELLOW, or RED
                else:
                    light = 'RED'
                    
                self.after(0, v.update, light, car_ahead)
                
            # 3. Garbage Collect off-screen cars
            for v in self.vehicles[:]:
                if v.is_off_screen():
                    self.canvas.delete(v.rect)
                    if v.is_emergency:
                        self.canvas.delete(v.beacon)
                        self.controller.emergency[v.road_origin] = False
                    self.vehicles.remove(v)
            
            # 4. Smart Math Live Update
            # Count actively queued cars (cars sitting at red light)
            for road in self.controller.roads:
                count = sum(1 for v in road_cars[road] if v.is_waiting() or v.speed < v.max_speed * 0.8)
                self.controller.waiting_counts[road] = count
                
                # Push the live sandbox count to our Flask backend so it calculates AI correctly!
                if self.simulation_running:
                    self.controller.push_mock_data(road, count)
                
                # Update text overlays safely via Tkinter main loop
                self.after(0, self.canvas.itemconfig, self.ui_texts[road], {"text": f"{road} Queued: {count}"})

            # Force graph redraw if not simulating to show updates
            if not self.simulation_running:
                self.controller.calculate_green_times()
                # Throttled graph render so we don't spam Tkinter at 60fps
                if self.vehicle_id_counter % 30 == 0: 
                    self.after(0, self.update_graphs)

            time.sleep(1.0 / FPS)
            
            # Since we deleted traffic_light_loop, we just sync UI right here in the master loop
            if self.simulation_running:
                new_emgs = self.controller.fetch_api_state()
                for road in new_emgs:
                    self.spawn_emergency(road, push_api=False)
                self.after(0, self.update_light_ui)
                self.after(0, self.update_graphs)

    # traffic_light_loop removed as backend controls states now
                
    def update_light_ui(self):
        """Updates the visual colors of the canvas UI lights."""
        active_road = self.controller.current_active_road
        state = self.controller.state
        
        # Update traffic light visual blobs
        for road in self.controller.roads:
            if not self.simulation_running:
                color = "red"
            elif road == active_road:
                color = "lime" if state == 'GREEN' else "yellow" if state == 'YELLOW' else "red"
            else:
                color = "red"
            self.canvas.itemconfig(self.ui_lights[road], fill=color)

        # Update Center Timer
        if self.simulation_running and not any(self.controller.emergency.values()):
            self.canvas.itemconfig(self.center_timer, text=str(max(0, self.controller.time_left)))
            self.canvas.itemconfig(self.center_timer, fill="lime" if state == 'GREEN' else "yellow")
        elif any(self.controller.emergency.values()):
            self.canvas.itemconfig(self.center_timer, text="EMG", fill="red")
        else:
            self.canvas.itemconfig(self.center_timer, text="-", fill="gray")

    def update_graphs_initial(self):
        self.update_graphs()

    def update_graphs(self):
        self.ax1.clear()
        self.ax1.set_facecolor('#1f2937')

        roads = [r[0] for r in self.controller.roads] # N, S, E, W
        times = [self.controller.calculated_green_times[r] for r in self.controller.roads]
        
        self.ax1.bar(roads, times, color='#10b981')
        self.ax1.set_title('AI Green Timer Map', color='white', size=10)
        self.ax1.tick_params(colors='white', labelsize=8)
        
        self.fig.tight_layout()
        self.canvas_graph.draw()

    def toggle_simulation(self):
        if self.simulation_running:
            self.simulation_running = False
            self.sim_btn.config(text="Start Signal Cycle", bg="#10b981")
        else:
            self.simulation_running = True
            self.sim_btn.config(text="Stop Signal Cycle", bg="#ef4444")

if __name__ == "__main__":
    app = GameTrafficDashboard()
    app.mainloop()
