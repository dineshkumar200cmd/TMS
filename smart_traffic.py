import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading

CYCLE_TIME = 120  # 120 seconds total cycle time

class SmartTrafficController:
    """Core logic for calculating green times dynamically."""
    
    def __init__(self):
        self.roads = ['A', 'B', 'C', 'D']
        self.vehicle_counts = {'A': 10, 'B': 10, 'C': 10, 'D': 10}
        self.emergency = {'A': False, 'B': False, 'C': False, 'D': False}
        self.calculated_green_times = {'A': 30, 'B': 30, 'C': 30, 'D': 30}
        self.fixed_green_times = {'A': 30, 'B': 30, 'C': 30, 'D': 30} # Baseline for comparison
        self.current_active_road = 'A'
        self.time_remaining = 0

    def calculate_green_times(self):
        """Dynamic Green Time = (vehicles / total) * 120s"""
        total_vehicles = sum(self.vehicle_counts.values())
        
        # Check for emergencies first
        for road in self.roads:
            if self.emergency[road]:
                # Emergency override: give this road 30s immediately, set others to 0s for this calculation
                self.calculated_green_times = {r: (30 if r == road else 0) for r in self.roads}
                return

        # Normal Dynamic Logic
        if total_vehicles == 0:
            # Prevent Division by Zero, default to equal split if empty
            self.calculated_green_times = {r: 30 for r in self.roads}
            return
            
        for road, count in self.vehicle_counts.items():
            # Formula: (vehicles on road / total vehicles) * total cycle time
            green_time = (count / total_vehicles) * CYCLE_TIME
            
            # Enforce safety limits
            if green_time < 5 and count > 0:
                green_time = 5  # Give at least 5 seconds if someone is waiting
            if count == 0:
                green_time = 0  # No vehicles = skip turn to save time
                
            self.calculated_green_times[road] = round(green_time)


class TrafficDashboard(tk.Tk):
    """Tkinter application managing the GUI and simulation loop."""

    def __init__(self):
        super().__init__()
        self.title("AI-Based Smart Traffic Management System")
        self.geometry("1000x800")
        self.configure(bg="#2d2d2d")
        
        self.controller = SmartTrafficController()
        self.simulation_running = False
        
        self.setup_ui()
        self.update_graphs_initial()

    def setup_ui(self):
        # Top Frame: Inputs
        input_frame = tk.LabelFrame(self, text="Vehicle Sensors & Emergency Inputs", bg="#2d2d2d", fg="white", font=('Arial', 12, 'bold'))
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.truck_vars = {}
        self.emg_vars = {}
        
        for idx, road in enumerate(self.controller.roads):
            frame = tk.Frame(input_frame, bg="#2d2d2d")
            frame.grid(row=0, column=idx, padx=20, pady=10)
            
            tk.Label(frame, text=f"Road {road} Vehicles:", bg="#2d2d2d", fg="white").pack()
            var = tk.IntVar(value=10)
            tk.Entry(frame, textvariable=var, width=5).pack()
            self.truck_vars[road] = var
            
            emg_var = tk.BooleanVar(value=False)
            tk.Checkbutton(frame, text="🚑 Emergency", variable=emg_var, bg="#2d2d2d", fg="red", selectcolor="black").pack()
            self.emg_vars[road] = emg_var

        btn_frame = tk.Frame(input_frame, bg="#2d2d2d")
        btn_frame.grid(row=0, column=4, padx=20)
        tk.Button(btn_frame, text="Update Data & Recalculate", command=self.update_data, bg="#0066cc", fg="white", font=('Arial', 10, 'bold')).pack(pady=5)
        self.sim_btn = tk.Button(btn_frame, text="Start Simulation", command=self.toggle_simulation, bg="#00cc66", fg="white", font=('Arial', 10, 'bold'))
        self.sim_btn.pack(pady=5)

        # Middle Frame: Traffic Light Visualization
        self.viz_frame = tk.Frame(self, bg="#1a1a1a", height=200)
        self.viz_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.lights = {}
        for idx, road in enumerate(self.controller.roads):
            lf = tk.Frame(self.viz_frame, bg="#1a1a1a", width=100)
            lf.grid(row=0, column=idx, padx=40, pady=20)
            tk.Label(lf, text=f"ROAD {road}", bg="#1a1a1a", fg="white", font=('Arial', 14, 'bold')).pack()
            
            canvas = tk.Canvas(lf, width=60, height=120, bg="black", highlightthickness=2, highlightbackground="grey")
            canvas.pack()
            
            # Draw red and green lights
            red = canvas.create_oval(10, 10, 50, 50, fill="darkred")
            green = canvas.create_oval(10, 70, 50, 110, fill="darkgreen")
            self.lights[road] = {'canvas': canvas, 'red': red, 'green': green}
            
            # Label for timer
            timer_lbl = tk.Label(lf, text="Waiting...", bg="#1a1a1a", fg="cyan", font=('Arial', 12))
            timer_lbl.pack(pady=5)
            self.lights[road]['timer'] = timer_lbl

        # Bottom Frame: Matplotlib Graphs
        self.graph_frame = tk.Frame(self, bg="white")
        self.graph_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(10, 3))
        self.fig.patch.set_facecolor('#ffffff')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_data(self):
        """Read values from UI into controller and recalculate."""
        for road in self.controller.roads:
            try:
                self.controller.vehicle_counts[road] = int(self.truck_vars[road].get())
            except ValueError:
                self.controller.vehicle_counts[road] = 0
            self.controller.emergency[road] = self.emg_vars[road].get()
            
        self.controller.calculate_green_times()
        self.update_graphs()

    def update_graphs_initial(self):
        """Draw empty graphs on boot"""
        self.update_graphs()

    def update_graphs(self):
        self.ax1.clear()
        self.ax2.clear()

        roads = self.controller.roads
        smart_times = [self.controller.calculated_green_times[r] for r in roads]
        fixed_times = [self.controller.fixed_green_times[r] for r in roads]

        # Graph 1: Green Time Allocation
        x = range(len(roads))
        width = 0.35
        self.ax1.bar([i - width/2 for i in x], fixed_times, width, label='Fixed Timer', color='grey')
        self.ax1.bar([i + width/2 for i in x], smart_times, width, label='AI Smart Timer', color='royalblue')
        self.ax1.set_title('Green Time Allocation per Road (seconds)')
        self.ax1.set_xticks(x)
        self.ax1.set_xticklabels(roads)
        self.ax1.legend()

        # Graph 2: Efficiency (Mock Data based on vehicles processed vs waiting)
        # Efficiency = (Green Time * Flow Rate) / Cars
        # Simplification: Higher green time to higher car count = better efficiency
        total_cars = sum(self.controller.vehicle_counts.values()) or 1
        
        fixed_eff = sum(30 * (c/total_cars) for c in self.controller.vehicle_counts.values())
        smart_eff = sum(self.controller.calculated_green_times[r] * (c/total_cars) for r, c in self.controller.vehicle_counts.items())

        self.ax2.bar(['Fixed System', 'AI System'], [fixed_eff, smart_eff], color=['grey', 'forestgreen'])
        self.ax2.set_title('Overall Traffic Throughput Efficiency')
        
        self.fig.tight_layout()
        self.canvas.draw()

    def toggle_simulation(self):
        if self.simulation_running:
            self.simulation_running = False
            self.sim_btn.config(text="Start Simulation", bg="#00cc66")
        else:
            self.simulation_running = True
            self.sim_btn.config(text="Stop Simulation", bg="#cc0000")
            self.update_data()
            threading.Thread(target=self.simulation_loop, daemon=True).start()

    def simulation_loop(self):
        """Runs the traffic light state machine in a background thread."""
        while self.simulation_running:
            for road in self.controller.roads:
                if not self.simulation_running: break
                
                # Check for emergency bypass in real-time
                if any(self.emg_vars[r].get() for r in self.controller.roads):
                    # Find emergency road
                    emg_road = next(r for r in self.controller.roads if self.emg_vars[r].get())
                    if road != emg_road:
                        continue # Skip to the emergency road

                self.controller.current_active_road = road
                green_time = self.controller.calculated_green_times[road]
                
                if green_time <= 0:
                    continue # Skip empty roads
                
                self.set_lights(road) # Turns this road green, others red
                
                # Countdown timer
                for t in range(int(green_time), 0, -1):
                    if not self.simulation_running: break
                    
                    # If an emergency pops up mid-cycle on another road, break immediately
                    if any(self.emg_vars[r].get() for r in self.controller.roads if r != road):
                        break

                    # Update GUI timer safely
                    self.after(0, self.update_timer_label, road, t)
                    time.sleep(1)
                
                self.after(0, self.update_timer_label, road, 0)
                
                # Recalculate data after every cycle segment in case inputs changed
                self.after(0, self.update_data)

    def update_timer_label(self, road, time_left):
        self.lights[road]['timer'].config(text=f"{time_left}s remaining", fg=("lime" if time_left > 0 else "cyan"))

    def set_lights(self, active_road):
        """Updates canvas elements for the traffic lights."""
        def tk_update():
            for road in self.controller.roads:
                canvas = self.lights[road]['canvas']
                red = self.lights[road]['red']
                green = self.lights[road]['green']
                
                if road == active_road:
                    canvas.itemconfig(red, fill="darkred")
                    canvas.itemconfig(green, fill="lime")
                else:
                    canvas.itemconfig(red, fill="red")
                    canvas.itemconfig(green, fill="darkgreen")
                    self.lights[road]['timer'].config(text="Waiting...", fg="cyan")
                    
        self.after(0, tk_update)


if __name__ == "__main__":
    app = TrafficDashboard()
    app.mainloop()
