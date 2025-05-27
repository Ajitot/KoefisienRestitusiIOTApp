import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import paho.mqtt.client as mqtt
import numpy as np
import json

time_data = []
voltage_data = []
collecting = False

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "telemed/ekg"

client = mqtt.Client()

root = tk.Tk()
root.title("Telemedicine EKG - Subscriber")

fig = Figure(figsize=(8, 4), dpi=100)
ax = fig.add_subplot(111, label="EKG")
line, = ax.plot([], [], label="EKG")
peaks_line, = ax.plot([], [], "ro", label="R-peak")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (mV)")
ax.legend()

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack()

def bandpass_filter(data, lowcut=0.5, highcut=40, fs=500, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

def on_message(client, userdata, msg):
    global time_data, voltage_data, collecting
    if collecting:
        try:
            payload = json.loads(msg.payload.decode())
            t = payload["time"]
            v = payload["voltage"]
            time_data.append(t)
            voltage_data.append(v)
        except:
            pass

def start_collection():
    global collecting
    collecting = True

def stop_collection():
    global collecting
    collecting = False

def reset_data():
    global time_data, voltage_data
    time_data.clear()
    voltage_data.clear()
    line.set_data([], [])
    peaks_line.set_data([], [])
    canvas.draw()

def save_excel():
    filename = filedialog.asksaveasfilename(defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")])
    if filename:
        df = pd.DataFrame({
            "Time (s)": [str(round(t, 3)) for t in time_data],
            "Voltage (mV)": voltage_data
        })
        df.to_excel(filename, index=False)

def save_png():
    filename = filedialog.asksaveasfilename(defaultextension=".png",
                filetypes=[("PNG files", "*.png")])
    if filename:
        fig.savefig(filename)

def close_app():
    client.loop_stop()
    root.destroy()

def update_plot(i):
    if not time_data:
        return
    filtered = bandpass_filter(voltage_data)
    line.set_data(time_data, filtered)
    ax.set_xlim(time_data[0], time_data[-1])
    ax.set_ylim(min(filtered), max(filtered))
    peaks, _ = find_peaks(filtered, distance=100)
    peak_times = [time_data[p] for p in peaks]
    peak_values = [filtered[p] for p in peaks]
    peaks_line.set_data(peak_times, peak_values)
    canvas.draw()

def init_mqtt():
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()

tk.Button(root, text="Start", command=start_collection).pack(side=tk.LEFT)
tk.Button(root, text="Stop", command=stop_collection).pack(side=tk.LEFT)
tk.Button(root, text="Reset", command=reset_data).pack(side=tk.LEFT)
tk.Button(root, text="Save Excel", command=save_excel).pack(side=tk.LEFT)
tk.Button(root, text="Save PNG", command=save_png).pack(side=tk.LEFT)
tk.Button(root, text="Exit", command=close_app).pack(side=tk.RIGHT)

ani = FuncAnimation(fig, update_plot, interval=500)
init_mqtt()
root.mainloop()