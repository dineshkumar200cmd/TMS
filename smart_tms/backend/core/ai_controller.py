class SmartTrafficController:
    """Core logic for calculating green times dynamically."""
    
    def __init__(self, cycle_time=120):
        self.cycle_time = cycle_time
        self.roads = ['North', 'South', 'East', 'West']
        self.vehicle_counts = {r: 0 for r in self.roads}
        self.emergency = {r: False for r in self.roads}
        self.calculated_green_times = {r: 30 for r in self.roads}
        self.fixed_green_times = {r: 30 for r in self.roads}
        
    def calculate_green_times(self):
        total_vehicles = sum(self.vehicle_counts.values())
        
        # 1. Emergency Override Logic
        for road in self.roads:
            if self.emergency[road]:
                self.calculated_green_times = {r: (self.cycle_time if r == road else 0) for r in self.roads}
                return

        # 2. Standard Dynamic Logic
        if total_vehicles == 0:
            self.calculated_green_times = {r: 30 for r in self.roads}
            return
            
        for road, count in self.vehicle_counts.items():
            green_time = (count / total_vehicles) * self.cycle_time
            if green_time < 5 and count > 0: 
                green_time = 5
            if count == 0: 
                green_time = 0
            self.calculated_green_times[road] = round(green_time)
