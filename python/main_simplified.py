import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
import time
import random

class DistanceMonitor:
    def __init__(self):
        self.time_data = []
        self.distance_data = []
        self.collecting = False
        self.start_time = None
        
        self.setup_gui()
        
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Distance Monitor - Simplified")
        self.root.geometry("800x600")
        
        # Plot setup
        self.fig = Figure(figsize=(10, 6))
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Distance (cm)")
        self.ax.set_title("Distance Measurement")
        self.ax.grid(True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Status
        self.status_label = tk.Label(self.root, text="Ready", font=("Arial", 12))
        self.status_label.pack(pady=5)
        
        # Controls
        self.setup_controls()
        
    def setup_controls(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=10)
        
        tk.Button(frame, text="Start", command=self.start, bg="lightgreen", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Stop", command=self.stop, bg="lightcoral", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Clear", command=self.clear, bg="lightyellow", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Save Data", command=self.save_data, bg="lightblue", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Generate Test", command=self.generate_test, bg="orange", width=10).pack(side=tk.LEFT, padx=5)
        
    def start(self):
        self.collecting = True
        self.start_time = time.time()
        self.status_label.config(text="Collecting data...")
        self.update_plot()
        
    def stop(self):
        self.collecting = False
        self.status_label.config(text="Stopped")
        
    def clear(self):
        self.time_data.clear()
        self.distance_data.clear()
        self.start_time = None
        self.update_plot()
        self.status_label.config(text="Data cleared")
        
    def add_data_point(self, distance):
        if self.start_time is None:
            self.start_time = time.time()
        
        current_time = time.time() - self.start_time
        self.time_data.append(current_time)
        self.distance_data.append(distance)
        
        if self.collecting:
            self.update_plot()
            
    def update_plot(self):
        self.ax.clear()
        
        if self.time_data and self.distance_data:
            self.ax.plot(self.time_data, self.distance_data, 'b-', linewidth=2)
            
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Distance (cm)")
        self.ax.set_title(f"Distance Measurement ({len(self.distance_data)} points)")
        self.ax.grid(True)
        
        self.canvas.draw()
        
    def generate_test(self):
        # Generate simple bouncing ball data
        if not self.collecting:
            self.start()
            
        for i in range(50):
            # Simple sine wave to simulate bouncing
            t = i * 0.1
            distance = 20 + 10 * abs(np.sin(t * 2))
            noise = random.uniform(-0.5, 0.5)
            distance += noise
            
            self.add_data_point(distance)
            
        self.status_label.config(text="Test data generated")
        
    def save_data(self):
        if not self.time_data:
            messagebox.showwarning("Warning", "No data to save")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        
        if filename:
            try:
                df = pd.DataFrame({
                    "Time (s)": self.time_data,
                    "Distance (cm)": self.distance_data
                })
                
                if filename.endswith('.xlsx'):
                    df.to_excel(filename, index=False)
                else:
                    df.to_csv(filename, index=False)
                    
                messagebox.showinfo("Success", f"Data saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving: {e}")
                
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)
        self.root.mainloop()

if __name__ == "__main__":
    app = DistanceMonitor()
    app.run()
