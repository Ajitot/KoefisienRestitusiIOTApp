import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import paho.mqtt.client as mqtt
import numpy as np
import json
import time
import random

# Global variables
time_data = []
distance_data = []
collecting = False
start_time = None
update_needed = False

# MQTT Configuration - Compatible with ESP8266 and ESP32
MQTT_BROKER = "broker.hivemq.com"  # Public broker for testing
MQTT_TOPIC = "sensor/distance"     # Generic topic name
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# Initialize MQTT client - Compatible with both ESP versions
try:
    # Try new API first (for newer paho-mqtt versions)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except:
    # Fallback to old API (for older paho-mqtt versions)
    client = mqtt.Client()

# GUI components
root = None
fig = None
ax = None
canvas = None
status_label = None
data_count_label = None
latest_data_label = None

def lowpass_filter(data, cutoff=5, fs=20, order=4):
    """Apply low-pass filter to smooth distance data"""
    min_length = max(order * 6, 20)
    if len(data) < min_length:
        return data
    
    try:
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        return filtfilt(b, a, data)
    except ValueError as e:
        print(f"Filter error: {e}")
        return data

def detect_bounces(distance_data, time_data, min_height=5, min_distance=10):
    """Detect ball bounces from distance data"""
    if len(distance_data) < 20:
        return [], []
    
    try:
        inverted = [-d for d in distance_data]
        peaks, _ = find_peaks(inverted, height=-min_height, distance=min_distance)
        
        bounce_times = [time_data[p] for p in peaks if p < len(time_data)]
        bounce_distances = [distance_data[p] for p in peaks if p < len(distance_data)]
        
        return bounce_times, bounce_distances
    except Exception as e:
        print(f"Bounce detection error: {e}")
        return [], []

def calculate_restitution_coefficient():
    """Calculate coefficient of restitution from bounce data"""
    if len(distance_data) < 50:
        messagebox.showwarning("Warning", "Not enough data to calculate coefficient")
        return
    
    try:
        filtered_data = lowpass_filter(distance_data)
        bounce_times, bounce_distances = detect_bounces(filtered_data, time_data)
        
        if len(bounce_distances) < 2:
            messagebox.showwarning("Warning", "Need at least 2 bounces to calculate coefficient")
            return
        
        max_distance = max(filtered_data)
        heights = [max_distance - d for d in bounce_distances]
        
        coefficients = []
        for i in range(1, len(heights)):
            if heights[i-1] > 0:
                e = np.sqrt(heights[i] / heights[i-1])
                coefficients.append(e)
        
        if coefficients:
            avg_coefficient = np.mean(coefficients)
            result_text = f"Coefficient of Restitution Analysis:\n"
            result_text += f"Number of bounces detected: {len(heights)}\n"
            result_text += f"Heights: {[round(h, 2) for h in heights]} cm\n"
            result_text += f"Individual coefficients: {[round(c, 3) for c in coefficients]}\n"
            result_text += f"Average coefficient: {round(avg_coefficient, 3)}\n"
            
            messagebox.showinfo("Restitution Coefficient", result_text)
        else:
            messagebox.showwarning("Warning", "Could not calculate coefficient")
            
    except Exception as e:
        messagebox.showerror("Error", f"Error calculating coefficient: {str(e)}")

def on_connect(client, userdata, flags, reason_code, properties=None):
    """MQTT connection callback - compatible with ESP8266/ESP32"""
    if reason_code == 0:
        print("Connected to MQTT Broker!")
        # Subscribe ke topik data untuk menerima sensor data
        client.subscribe(MQTT_TOPIC)
        # Subscribe ke topik command untuk debugging (opsional)
        client.subscribe(MQTT_TOPIC + "/cmd")
        status_label.config(text="Status: Connected to MQTT", fg="blue")
        print(f"Subscribed to: {MQTT_TOPIC} and {MQTT_TOPIC}/cmd")
    else:
        print(f"Failed to connect, reason code {reason_code}")
        status_label.config(text="Status: MQTT Connection Failed", fg="red")

def on_disconnect(client, userdata, flags, reason_code, properties=None):
    """MQTT disconnection callback"""
    print("Disconnected from MQTT Broker")
    status_label.config(text="Status: MQTT Disconnected", fg="orange")

def on_message(client, userdata, msg):
    """Process incoming MQTT messages from ESP8266/ESP32"""
    global time_data, distance_data, collecting, start_time, update_needed
    
    if not collecting:
        return
        
    try:
        # Try to parse as JSON first
        try:
            payload = json.loads(msg.payload.decode())
            print(f"Received JSON: {payload}")
            
            # Handle different message formats from ESP devices
            if isinstance(payload, dict):
                # Modern format with multiple fields
                t = payload.get("timestamp", payload.get("time", 0))
                d = payload.get("distance", payload.get("dist", 0))
                device = payload.get("device", payload.get("id", "ESP_Device"))
                
                # Handle status messages
                if "status" in payload or "error" in payload:
                    print(f"Device message: {payload}")
                    return
            else:
                print(f"Unexpected payload format: {payload}")
                return
                
        except json.JSONDecodeError:
            # Handle simple text format: "distance:25.4"
            msg_str = msg.payload.decode().strip()
            print(f"Received text: {msg_str}")
            
            if ":" in msg_str:
                parts = msg_str.split(":")
                if len(parts) == 2 and parts[0].lower() in ["distance", "dist"]:
                    try:
                        d = float(parts[1])
                        t = 0
                        device = "ESP_Text"
                    except ValueError:
                        print(f"Invalid distance value: {parts[1]}")
                        return
                else:
                    print(f"Unknown text format: {msg_str}")
                    return
            else:
                # Try direct number
                try:
                    d = float(msg_str)
                    t = 0
                    device = "ESP_Raw"
                except ValueError:
                    print(f"Cannot parse message: {msg_str}")
                    return
        
        # Validate distance data
        if not isinstance(d, (int, float)) or d <= 0 or d > 400:
            print(f"Distance out of range: {d}")
            return
        
        # Handle timestamp
        if t > 0:
            # Use ESP provided timestamp
            current_time = float(t)
        else:
            # Generate local timestamp
            if start_time is None:
                start_time = time.time()
            current_time = time.time() - start_time
        
        # Store data
        time_data.append(current_time)
        distance_data.append(float(d))
        update_needed = True
        
        # Update GUI
        data_count_label.config(text=f"Data Points: {len(distance_data)}")
        latest_data_label.config(text=f"Latest: {d:.1f}cm @ {current_time:.2f}s [{device}]")
        
        print(f"Stored: Time={current_time:.2f}s, Distance={d}cm, Device={device}")
        
    except Exception as e:
        print(f"Error processing message: {e}")

def send_mqtt_command(command):
    """Send command to ESP8266/ESP32"""
    try:
        if client.is_connected():
            # Send to command topic
            command_topic = MQTT_TOPIC + "/cmd"
            result = client.publish(command_topic, command)
            print(f"Sent command to {command_topic}: {command}")
            print(f"Publish result: {result.rc}")
            status_label.config(text=f"Status: Command sent - {command}", fg="blue")
            return True
        else:
            print("MQTT not connected")
            messagebox.showwarning("Warning", "MQTT not connected")
            return False
    except Exception as e:
        print(f"Error sending command: {e}")
        return False

def setup_mqtt():
    """Setup MQTT client with ESP8266/ESP32 compatibility"""
    try:
        # Set callbacks
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        
        print(f"Connecting to MQTT broker: {MQTT_BROKER}")
        client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        client.loop_start()
        
    except Exception as e:
        print(f"MQTT Setup Error: {str(e)}")
        status_label.config(text="Status: MQTT Setup Failed", fg="red")

def start_collection():
    """Start data collection"""
    global collecting, start_time, update_needed
    collecting = True
    start_time = time.time()
    update_needed = True
    status_label.config(text="Status: Collecting", fg="green")
    
    # Kirim perintah ke ESP untuk mulai
    send_mqtt_command("START_READING")
    print("Data collection started")

def stop_collection():
    """Stop data collection"""
    global collecting, update_needed
    collecting = False
    update_needed = True
    status_label.config(text="Status: Stopped", fg="red")
    
    # Kirim perintah ke ESP untuk berhenti
    send_mqtt_command("STOP_READING")
    print("Data collection stopped")

def reset_data():
    """Reset all collected data"""
    global time_data, distance_data, start_time, update_needed
    time_data.clear()
    distance_data.clear()
    start_time = None
    update_needed = True
    data_count_label.config(text="Data Points: 0")
    latest_data_label.config(text="Latest: -")
    status_label.config(text="Status: Data Reset", fg="blue")
    update_plot()
    print("Data has been reset.")

def update_plot():
    """Update the matplotlib plot"""
    try:
        if len(time_data) == 0:
            ax.clear()
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Distance (cm)")
            ax.set_title("Real-time Distance Measurement")
            ax.grid(True, alpha=0.3)
            canvas.draw_idle()
            return
        
        ax.clear()
        
        # Apply filter if enough data
        if len(distance_data) > 20:
            filtered = lowpass_filter(distance_data)
        else:
            filtered = distance_data
        
        # Plot main line
        ax.plot(time_data, filtered, 'b-', label="Distance", linewidth=2)
        
        # Show bounces if enough data
        if len(filtered) > 30:
            bounce_times, bounce_distances = detect_bounces(filtered, time_data)
            if bounce_times and bounce_distances:
                ax.plot(bounce_times, bounce_distances, "ro", label="Peaks", markersize=6)
        
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Distance (cm)")
        ax.set_title("Real-time Distance Measurement")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Set axis limits
        if len(time_data) > 1:
            time_range = max(max(time_data) - min(time_data), 1)
            x_margin = time_range * 0.05
            ax.set_xlim(min(time_data) - x_margin, max(time_data) + x_margin)
        
        if len(filtered) > 1:
            dist_range = max(max(filtered) - min(filtered), 5)
            y_margin = dist_range * 0.1
            ax.set_ylim(min(filtered) - y_margin, max(filtered) + y_margin)
        
        canvas.draw_idle()
        
    except Exception as e:
        print(f"Plot update error: {e}")

def periodic_update():
    """Periodic update for real-time display"""
    global update_needed
    
    try:
        if update_needed and len(time_data) >= 0:
            update_plot()
            update_needed = False
        
        root.update_idletasks()
        
    except Exception as e:
        print(f"Periodic update error: {e}")
    
    # Schedule next update
    interval = 50 if collecting or len(time_data) > 0 else 200
    root.after(interval, periodic_update)

def set_interval():
    """Set sensor reading interval"""
    try:
        interval = simpledialog.askinteger("Set Interval", 
                                         "Enter interval in milliseconds (50-5000):",
                                         initialvalue=100, minvalue=50, maxvalue=5000)
        if interval:
            send_mqtt_command(f"INTERVAL:{interval}")
    except Exception as e:
        print(f"Error setting interval: {e}")

def save_excel():
    """Save collected data to an Excel file."""
    if not time_data or not distance_data:
        messagebox.showwarning("Warning", "No data to save.")
        return
    try:
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            df = pd.DataFrame({"Time (s)": time_data, "Distance (cm)": distance_data})
            df.to_excel(file_path, index=False)
            messagebox.showinfo("Success", f"Data saved to {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save data: {e}")

def save_png():
    """Save the current plot as a PNG file."""
    try:
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path:
            fig.savefig(file_path)
            messagebox.showinfo("Success", f"Plot saved to {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save plot: {e}")

def close_app():
    """Handle application close event"""
    try:
        if client.is_connected():
            client.loop_stop()
            client.disconnect()
    except Exception as e:
        print(f"Error during disconnect: {e}")
    if root is not None:
        root.destroy()

def setup_gui():
    """Initialize GUI components"""
    global root, fig, ax, canvas, status_label, data_count_label, latest_data_label
    
    root = tk.Tk()
    root.title("HC-SR04 Distance Monitor - ESP8266/ESP32 Compatible")
    root.protocol("WM_DELETE_WINDOW", close_app)
    
    # Setup plot
    fig = Figure(figsize=(10, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Distance (cm)")
    ax.set_title("Real-time Distance Measurement")
    ax.grid(True, alpha=0.3)
    
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # Status frame
    status_frame = tk.Frame(root)
    status_frame.pack(fill=tk.X, padx=5, pady=5)
    
    status_label = tk.Label(status_frame, text="Status: Stopped", font=("Arial", 12, "bold"))
    status_label.pack(side=tk.LEFT)
    
    data_count_label = tk.Label(status_frame, text="Data Points: 0", font=("Arial", 10))
    data_count_label.pack(side=tk.RIGHT)
    
    latest_data_label = tk.Label(status_frame, text="Latest: -", font=("Arial", 9))
    latest_data_label.pack(side=tk.RIGHT, padx=10)
    
    # Main controls
    button_frame = tk.Frame(root)
    button_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Button(button_frame, text="Start", command=start_collection, bg="lightgreen").pack(side=tk.LEFT, padx=2)
    tk.Button(button_frame, text="Stop", command=stop_collection, bg="lightcoral").pack(side=tk.LEFT, padx=2)
    tk.Button(button_frame, text="Reset", command=reset_data, bg="lightyellow").pack(side=tk.LEFT, padx=2)
    tk.Button(button_frame, text="Refresh Plot", command=lambda: [setattr(globals(), 'update_needed', True), update_plot()], bg="lightcyan").pack(side=tk.LEFT, padx=2)
    tk.Button(button_frame, text="Save Data", command=save_excel, bg="lightblue").pack(side=tk.LEFT, padx=2)
    tk.Button(button_frame, text="Save Plot", command=save_png, bg="lightblue").pack(side=tk.LEFT, padx=2)
    tk.Button(button_frame, text="Calculate Coefficient", command=calculate_restitution_coefficient, bg="orange").pack(side=tk.LEFT, padx=2)
    
    tk.Button(button_frame, text="Exit", command=close_app, bg="lightgray").pack(side=tk.RIGHT, padx=2)
    
    # ESP controls
    esp_frame = tk.Frame(root)
    esp_frame.pack(fill=tk.X, padx=5, pady=2)
    
    tk.Label(esp_frame, text="ESP8266/ESP32 Controls:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    tk.Button(esp_frame, text="Start ESP Reading", command=lambda: send_mqtt_command("START_READING"), bg="lightgreen").pack(side=tk.LEFT, padx=2)
    tk.Button(esp_frame, text="Stop ESP Reading", command=lambda: send_mqtt_command("STOP_READING"), bg="lightcoral").pack(side=tk.LEFT, padx=2)
    tk.Button(esp_frame, text="Request Distance", command=lambda: send_mqtt_command("READ_DISTANCE"), bg="lightyellow").pack(side=tk.LEFT, padx=2)
    tk.Button(esp_frame, text="Set Interval", command=set_interval, bg="lightcyan").pack(side=tk.LEFT, padx=2)

def main():
    """Main application entry point"""
    print("=== HC-SR04 Distance Monitor ===")
    print("Compatible with ESP8266 and ESP32")
    print(f"MQTT Broker: {MQTT_BROKER}")
    print(f"MQTT Topic: {MQTT_TOPIC}")
    print("=====================================")
    
    # Setup GUI
    setup_gui()
    
    # Setup MQTT
    setup_mqtt()
    
    # Start periodic updates
    root.after(100, periodic_update)
    
    print("Application started!")
    print("- Click 'Start' to begin data collection")
    print("- ESP devices should publish to topic:", MQTT_TOPIC)
    
    # Start GUI main loop
    root.mainloop()

if __name__ == "__main__":
    main()