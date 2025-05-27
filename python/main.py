import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
import paho.mqtt.client as mqtt
import numpy as np
import json
import time
import os

# Global variables
time_data = []
distance_data = []
collecting = False
start_time = None
update_needed = False
sensor_height = 35  # cm
selected_ball_type = "Bola Bekel"  # Default ball type

# Bounce detection parameters
bounce_threshold = 15.0  # minimum bounce height (cm) - PERBAIKAN: dari 5.0 ke 15.0
min_bounce_distance = 1  # minimum distance between bounces (data points)
min_height_difference = 0.1 # minimum height difference between consecutive peaks (cm)

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
data_tree = None
analysis_text = None

bola = ["Bola Bekel","Bola Tenis Meja", "Bola Tenis Lapang", 
        "Bola Plastik", "Bola Sepak Karet"]

# Global variables untuk analisis
latest_analysis_text = ""

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

def detect_bounces(distance_data, time_data, min_height=None, min_distance=None):
    """Detect ball bounce peaks (maximum heights) from distance data"""
    if len(distance_data) < 20:
        return [], []
    
    # Use global parameters if not provided
    if min_height is None:
        min_height = bounce_threshold
    if min_distance is None:
        min_distance = min_bounce_distance
    
    try:
        # Find peaks (maximum values) directly - no inversion needed
        peaks, properties = find_peaks(distance_data, 
                                     height=min_height,           # minimum peak height
                                     distance=min_distance,       # minimum distance between peaks
                                     prominence=3.0)              # PERBAIKAN: tingkatkan prominence dari 2.0 ke 3.0
        
        bounce_times = [time_data[p] for p in peaks if p < len(time_data)]
        bounce_distances = [distance_data[p] for p in peaks if p < len(distance_data)]
        
        # PERBAIKAN: Filter peaks berdasarkan selisih ketinggian minimal 1 cm dan trend menurun
        filtered_times = []
        filtered_distances = []
        
        if bounce_distances:
            # Tambahkan puncak pertama
            filtered_times.append(bounce_times[0])
            filtered_distances.append(bounce_distances[0])
            
            # Filter puncak selanjutnya berdasarkan selisih ketinggian dan trend menurun
            for i in range(1, len(bounce_distances)):
                height_diff = abs(bounce_distances[i] - filtered_distances[-1])
                
                # PERBAIKAN: Hanya tambahkan jika selisih ketinggian >= 1 cm DAN tinggi menurun (untuk pantulan alami)
                if height_diff >= min_height_difference and bounce_distances[i] <= filtered_distances[-1]:
                    filtered_times.append(bounce_times[i])
                    filtered_distances.append(bounce_distances[i])
                elif bounce_distances[i] > filtered_distances[-1]:
                    print(f"Puncak diabaikan: tinggi {bounce_distances[i]:.1f}cm > puncak sebelum {filtered_distances[-1]:.1f}cm (trend naik tidak wajar)")
                else:
                    print(f"Puncak diabaikan: tinggi {bounce_distances[i]:.1f}cm, selisih {height_diff:.1f}cm < {min_height_difference}cm")
        
        print(f"Detected {len(filtered_distances)} valid bounces at heights: {[round(h, 1) for h in filtered_distances]}")
        
        return filtered_times, filtered_distances
    except Exception as e:
        print(f"Bounce detection error: {e}")
        return [], []

def set_ball_type():
    """Set ball type from dropdown"""
    global selected_ball_type, update_needed
    
    # Create dialog window
    dialog = tk.Toplevel(root)
    dialog.title("Pilih Jenis Bola")
    dialog.geometry("300x200")
    dialog.resizable(False, False)
    
    # Center the dialog
    dialog.transient(root)
    dialog.grab_set()
    
    # Create frame
    frame = tk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    tk.Label(frame, text="Pilih jenis bola yang akan diuji:", 
             font=("Arial", 11, "bold")).pack(pady=(0, 10))
    
    # Dropdown variable
    ball_var = tk.StringVar(value=selected_ball_type)
    
    # Create dropdown
    ball_dropdown = ttk.Combobox(frame, textvariable=ball_var, 
                                values=bola, state="readonly", 
                                font=("Arial", 10), width=20)
    ball_dropdown.pack(pady=(0, 20))
    
    # Button frame
    button_frame = tk.Frame(frame)
    button_frame.pack(fill=tk.X)
    
    def apply_selection():
        global selected_ball_type, update_needed
        selected_ball_type = ball_var.get()
        update_needed = True
        status_label.config(text=f"Status: Jenis bola diatur ke {selected_ball_type}", fg="blue")
        print(f"Jenis bola diubah ke: {selected_ball_type}")
        dialog.destroy()
    
    def cancel_selection():
        dialog.destroy()
    
    tk.Button(button_frame, text="Terapkan", command=apply_selection, 
             bg="lightgreen", width=10, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
    tk.Button(button_frame, text="Batal", command=cancel_selection, 
             bg="lightcoral", width=10, font=("Arial", 10)).pack(side=tk.LEFT)

def calculate_restitution_coefficient():
    """Calculate coefficient of restitution from bounce data"""
    global latest_analysis_text
    
    if len(distance_data) < 10:
        messagebox.showwarning("Peringatan", "Tidak cukup data untuk menghitung koefisien\nMinimum diperlukan: 10 titik data")
        return
    
    # PERBAIKAN: Validasi data sebelum analisis
    if len(time_data) != len(distance_data):
        messagebox.showerror("Error", f"Ketidakcocokan data:\nWaktu: {len(time_data)}\nJarak: {len(distance_data)}")
        return
    
    # PERBAIKAN: Cek adanya NaN atau Inf
    if any(np.isnan(d) or np.isinf(d) for d in distance_data):
        messagebox.showerror("Error", "Data mengandung nilai tidak valid (NaN/Inf)")
        return
    
    if any(np.isnan(t) or np.isinf(t) for t in time_data):
        messagebox.showerror("Error", "Data waktu mengandung nilai tidak valid (NaN/Inf)")
        return
    
    try:
        # Use current data without additional filtering to preserve bounce patterns
        filtered_data = distance_data
        bounce_times, bounce_distances = detect_bounces(filtered_data, time_data)
        
        if len(bounce_distances) < 2:
            messagebox.showwarning("Peringatan", 
                                 f"Perlu setidaknya 2 pantulan untuk menghitung koefisien\n"
                                 f"Saat ini terdeteksi: {len(bounce_distances)} pantulan\n"
                                 f"Coba sesuaikan pengaturan:\n"
                                 f"- Ambang pantulan (saat ini: {bounce_threshold}cm)\n"
                                 f"- Selisih tinggi minimum (saat ini: {min_height_difference}cm)\n"
                                 f"CATATAN: Sistem otomatis mengabaikan puncak yang naik (tidak wajar)")
            return
        
        # PERBAIKAN: Validasi tambahan untuk ketinggian pantulan dan trend menurun
        valid_heights = [h for h in bounce_distances if h >= bounce_threshold]
        
        # PERBAIKAN: Validasi trend menurun untuk pantulan natural
        decreasing_trend = True
        for i in range(1, len(bounce_distances)):
            if bounce_distances[i] > bounce_distances[i-1]:
                decreasing_trend = False
                break
        
        if len(valid_heights) < 2:
            messagebox.showwarning("Peringatan", 
                                 f"Tidak cukup pantulan dengan ketinggian minimal {bounce_threshold}cm\n"
                                 f"Pantulan terdeteksi: {len(bounce_distances)}\n"
                                 f"Pantulan valid (>= {bounce_threshold}cm): {len(valid_heights)}\n"
                                 f"Trend menurun: {'Ya' if decreasing_trend else 'Tidak'}\n"
                                 f"Kurangi ambang pantulan atau lakukan pengukuran ulang")
            return
        
        # Calculate coefficients between consecutive bounces
        heights = bounce_distances  # Already ball heights from ground
        coefficients = []
        bounce_intervals = []
        
        for i in range(1, len(heights)):
            if heights[i-1] >= bounce_threshold and heights[i] >= bounce_threshold:  # PERBAIKAN: Validasi kedua ketinggian
                e = np.sqrt(heights[i] / heights[i-1])
                # PERBAIKAN: Validasi koefisien
                if not (np.isnan(e) or np.isinf(e)):
                    coefficients.append(e)
                    
                    # Calculate time interval between bounces
                    time_interval = bounce_times[i] - bounce_times[i-1]
                    bounce_intervals.append(time_interval)
        
        if coefficients:
            # Statistical analysis
            avg_coefficient = np.mean(coefficients)
            std_coefficient = np.std(coefficients)
            min_coefficient = np.min(coefficients)
            max_coefficient = np.max(coefficients)
            
            # PERBAIKAN: Validasi hasil statistik
            if any(np.isnan([avg_coefficient, std_coefficient, min_coefficient, max_coefficient])):
                messagebox.showerror("Error", "Hasil perhitungan mengandung nilai tidak valid")
                return
            
            # Energy loss calculation
            energy_retention = avg_coefficient ** 2  # e² = energy ratio
            energy_loss_percent = (1 - energy_retention) * 100
            
            # Material classification based on coefficient
            if avg_coefficient >= 0.9:
                material_type = "Super Ball / Elastisitas Tinggi"
                quality = "Sangat Baik"
            elif avg_coefficient >= 0.8:
                material_type = "Bola Karet / Elastisitas Baik"
                quality = "Baik Sekali"
            elif avg_coefficient >= 0.6:
                material_type = "Bola Tenis / Elastisitas Sedang"
                quality = "Baik"
            elif avg_coefficient >= 0.4:
                material_type = "Bola Lunak / Elastisitas Rendah"
                quality = "Cukup"
            else:
                material_type = "Material Sangat Lunak / Elastisitas Buruk"
                quality = "Buruk"
            
            # Format comprehensive results untuk tampilan di frame analisis
            latest_analysis_text = f"""
{'='*60}
    ANALISIS KOEFISIEN RESTITUSI - {selected_ball_type.upper()}
{'='*60}

PENGATURAN PENGUKURAN:
  • Jenis Bola yang Diuji        : {selected_ball_type}
  • Tinggi Sensor dari Lantai    : {sensor_height:.1f} cm
  • Ambang Deteksi Pantulan      : {bounce_threshold:.1f} cm
  • Selisih Tinggi Minimum       : {min_height_difference:.1f} cm
  • Jarak Minimum Pantulan       : {min_bounce_distance} titik data
  • Total Titik Data Terkumpul   : {len(distance_data)}
  • Durasi Pengukuran            : {max(time_data):.2f} detik
  • Waktu Mulai dari             : 0.00 detik (direset setiap mulai)

{'─'*60}
HASIL DETEKSI PANTULAN:
  • Jumlah Pantulan Terdeteksi   : {len(heights)}
  • Pantulan Valid (>= {bounce_threshold}cm) : {len(valid_heights)}
  • Trend Menurun (Natural)      : {'Ya' if decreasing_trend else 'Tidak'}
  • Tinggi Pantulan (cm)         : {', '.join([f'{h:.2f}' for h in heights])}
  • Waktu Pantulan (s)           : {', '.join([f'{t:.2f}' for t in bounce_times])}
  • Interval Waktu (s)           : {', '.join([f'{t:.3f}' for t in bounce_intervals])}

{'─'*60}
PERHITUNGAN KOEFISIEN:
"""
            
            # Add individual coefficient calculations - PERBAIKAN: hanya untuk pantulan valid
            valid_pairs = 0
            for i, (e, h_before, h_after, dt) in enumerate(zip(coefficients, heights[:-1], heights[1:], bounce_intervals)):
                if h_before >= bounce_threshold and h_after >= bounce_threshold:
                    valid_pairs += 1
                    latest_analysis_text += f"  Pantulan {i+1} → {i+2} (VALID - MENURUN):\n"
                    latest_analysis_text += f"    Tinggi: {h_before:.2f} cm → {h_after:.2f} cm\n"
                    latest_analysis_text += f"    Penurunan: {h_before - h_after:.2f} cm\n"
                    latest_analysis_text += f"    Koefisien: e = √({h_after:.2f}/{h_before:.2f}) = {e:.3f}\n"
                    latest_analysis_text += f"    Interval Waktu: {dt:.3f} detik\n"
                    latest_analysis_text += f"    Energi Tersisa: {(e**2)*100:.1f}%\n\n"
                else:
                    latest_analysis_text += f"  Pantulan {i+1} → {i+2} (DIABAIKAN):\n"
                    latest_analysis_text += f"    Tinggi: {h_before:.2f} cm → {h_after:.2f} cm\n"
                    latest_analysis_text += f"    Alasan: Ketinggian < {bounce_threshold}cm\n\n"
            
            latest_analysis_text += f"""{'─'*60}
RINGKASAN STATISTIK:
  • Pasangan Pantulan Valid      : {valid_pairs} dari {len(heights)-1} total
  • Koefisien Rata-rata (e)      : {avg_coefficient:.4f}
  • Standar Deviasi              : {std_coefficient:.4f}
  • Koefisien Minimum            : {min_coefficient:.4f}
  • Koefisien Maksimum           : {max_coefficient:.4f}
  • Rentang Koefisien            : {max_coefficient - min_coefficient:.4f}

ANALISIS ENERGI:
  • Retensi Energi Rata-rata     : {energy_retention*100:.2f}%
  • Kehilangan Energi Rata-rata  : {energy_loss_percent:.2f}%
  • Tingkat Disipasi Energi      : {energy_loss_percent:.1f}% per pantulan

{'─'*60}
KLASIFIKASI MATERIAL:
  • Perkiraan Jenis Material     : {material_type}
  • Kualitas Pantulan            : {quality}
  • Rating Elastisitas           : {avg_coefficient*100:.1f}%

{'─'*60}
HASIL UNTUK {selected_ball_type.upper()}:
  • Koefisien Restitusi          : {avg_coefficient:.3f}
  • Kualitas Pantulan            : {quality}
  • Retensi Energi               : {energy_retention*100:.1f}%

{'─'*60}
PERBANDINGAN TEORITIS:
  • Tumbukan Elastis Sempurna    : e = 1.000 (100% retensi energi)
  • {selected_ball_type} Anda          : e = {avg_coefficient:.3f} ({energy_retention*100:.1f}% retensi energi)
  • Tumbukan Inelastis Sempurna  : e = 0.000 (0% retensi energi)

CATATAN FISIKA:
  • Koefisien restitusi (e) mengukur elastisitas tumbukan
  • e = 1: Tumbukan elastis sempurna (tanpa kehilangan energi)
  • e = 0: Tumbukan inelastis sempurna (kehilangan energi maksimum)
  • Material nyata umumnya memiliki 0.1 < e < 0.95
  • Koefisien tinggi berarti karakteristik pantulan bola lebih baik

PENGATURAN FILTER:
  • Tinggi minimum pantulan: {bounce_threshold}cm
  • Selisih tinggi minimum: {min_height_difference}cm
  • Filter trend menurun: AKTIF (mengabaikan puncak yang naik)
  • Filter ini memastikan hanya pantulan natural yang dihitung

{'='*60}
Analisis {selected_ball_type} selesai pada: {time.strftime('%Y-%m-%d %H:%M:%S')}
Waktu pengukuran: 0.00 - {max(time_data):.2f} detik
{'='*60}
"""
            
            # Update tampilan analisis di frame
            update_analysis_display()
            
            # Show success message
            messagebox.showinfo("Berhasil", 
                              f"Analisis koefisien restitusi {selected_ball_type} selesai!\n\n"
                              f"Pantulan valid: {valid_pairs} dari {len(heights)} (trend menurun)\n"
                              f"Koefisien rata-rata: {avg_coefficient:.3f}\n"
                              f"Kualitas pantulan: {quality}\n"
                              f"Retensi energi: {energy_retention*100:.1f}%\n"
                              f"Durasi pengukuran: {max(time_data):.2f} detik\n\n"
                              f"Hasil lengkap ditampilkan di panel Analisis Real-time")
            
        else:
            messagebox.showwarning("Peringatan", "Tidak dapat menghitung koefisien\nTidak ditemukan pasangan pantulan yang valid")
            
    except Exception as e:
        messagebox.showerror("Error", f"Error menghitung koefisien:\n{str(e)}\n\nSilakan periksa data dan pengaturan Anda")
        print(f"Calculation error details: {e}")

def on_connect(client, userdata, flags, reason_code, properties=None):
    """MQTT connection callback - compatible with ESP8266/ESP32"""
    if reason_code == 0:
        print("Terhubung ke MQTT Broker!")
        # Subscribe ke topik data untuk menerima sensor data saja
        client.subscribe(MQTT_TOPIC)
        # HAPUS subscription ke command topic untuk menghindari loop
        status_label.config(text="Status: Terhubung ke MQTT", fg="blue")
        print(f"Berlangganan ke: {MQTT_TOPIC}")
    else:
        print(f"Gagal terhubung, kode alasan {reason_code}")
        status_label.config(text="Status: Koneksi MQTT Gagal", fg="red")

def on_disconnect(client, userdata, flags, reason_code, properties=None):
    """MQTT disconnection callback"""
    print("Terputus dari MQTT Broker")
    status_label.config(text="Status: MQTT Terputus", fg="orange")

def on_message(client, userdata, msg):
    """Process incoming MQTT messages from ESP8266/ESP32"""
    global time_data, distance_data, collecting, start_time, update_needed, sensor_height
    
    # Abaikan messages dari command topic untuk menghindari loop
    if msg.topic.endswith("/cmd"):
        print(f"Mengabaikan echo perintah: {msg.payload.decode()}")
        return
    
    if not collecting:
        return
        
    try:
        # Try to parse as JSON first
        try:
            payload = json.loads(msg.payload.decode())
            print(f"Menerima JSON: {payload}")
            
            # Handle different message formats from ESP devices
            if isinstance(payload, dict):
                # Modern format with multiple fields
                t = payload.get("timestamp", payload.get("time", 0))
                d = payload.get("distance", payload.get("dist", 0))
                device = payload.get("device", payload.get("id", "ESP_Device"))
                
                # Handle status messages
                if "status" in payload or "error" in payload:
                    print(f"Pesan perangkat: {payload}")
                    return
            else:
                print(f"Format payload tidak terduga: {payload}")
                return
                
        except json.JSONDecodeError:
            # Handle simple text format: "distance:25.4"
            msg_str = msg.payload.decode().strip()
            print(f"Menerima teks: {msg_str}")
            
            if ":" in msg_str:
                parts = msg_str.split(":")
                if len(parts) == 2 and parts[0].lower() in ["distance", "dist"]:
                    try:
                        d = float(parts[1])
                        t = 0
                        device = "ESP_Text"
                    except ValueError:
                        print(f"Nilai jarak tidak valid: {parts[1]}")
                        return
                else:
                    print(f"Format teks tidak dikenal: {msg_str}")
                    return
            else:
                # Try direct number
                try:
                    d = float(msg_str)
                    t = 0
                    device = "ESP_Raw"
                except ValueError:
                    print(f"Tidak dapat mengurai pesan: {msg_str}")
                    return
        
        # PERBAIKAN: Validasi data yang lebih ketat
        if not isinstance(d, (int, float)) or d <= 0 or d > 400:
            print(f"Jarak di luar rentang: {d}")
            return
        
        if not isinstance(t, (int, float)) or t < 0:
            print(f"Timestamp tidak valid: {t}")
            if t < 0:
                t = 0  # Reset ke 0 jika negatif
        
        # Convert distance to ball height (sensor_height - distance_reading)
        ball_height = sensor_height - d
        
        # Validate ball height (should be positive for bouncing ball)
        if ball_height < 0:
            print(f"Tinggi bola negatif: {ball_height:.1f}cm (sensor terlalu rendah?)")
            return
        
        # PERBAIKAN: Handle timestamp dengan reset ke 0 setiap mulai baru
        if t > 0:
            # Use ESP provided timestamp, but adjust to start from 0
            if start_time is None:
                start_time = time.time()
            # Jika menggunakan timestamp ESP, pastikan dimulai dari 0
            current_time = float(t)
        else:
            # Generate local timestamp starting from 0
            if start_time is None:
                start_time = time.time()
            current_time = time.time() - start_time
        
        # PERBAIKAN: Validasi final sebelum menyimpan
        if np.isnan(current_time) or np.isinf(current_time) or np.isnan(ball_height) or np.isinf(ball_height):
            print(f"Data mengandung NaN atau Inf, diabaikan")
            return
        
        # Store data (now storing ball height instead of raw distance)
        time_data.append(float(current_time))
        distance_data.append(float(ball_height))
        update_needed = True
        
        # Update GUI
        data_count_label.config(text=f"Jumlah Data: {len(distance_data)}")
        latest_data_label.config(text=f"Terbaru: {ball_height:.1f}cm @ {current_time:.2f}s [{device}]")
        
        print(f"Disimpan: Waktu={current_time:.2f}s, Tinggi Bola={ball_height:.1f}cm (Mentah={d:.1f}cm), Perangkat={device}")
        
    except Exception as e:
        print(f"Error memproses pesan: {e}")

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
    start_time = time.time()  # PERBAIKAN: Reset start_time setiap kali mulai
    update_needed = True
    status_label.config(text="Status: Mengumpulkan Data", fg="green")
    
    # PERBAIKAN: Reset data waktu agar dimulai dari 0
    if time_data:
        print("Mereset waktu ke 0 untuk pembacaan baru")
    
    # Kirim perintah ke ESP untuk mulai
    send_mqtt_command("START_READING")
    print("Pengumpulan data dimulai - waktu direset ke 0")

def stop_collection():
    """Stop data collection"""
    global collecting, update_needed
    collecting = False
    update_needed = True
    status_label.config(text="Status: Berhenti", fg="red")
    
    # Kirim perintah ke ESP untuk berhenti
    send_mqtt_command("STOP_READING")
    print("Pengumpulan data dihentikan")
    
    # Auto-calculate coefficient setelah pengumpulan data selesai
    if len(distance_data) >= 10:
        print("Menghitung koefisien restitusi otomatis...")
        root.after(1000, calculate_restitution_coefficient)  # Delay 1 detik untuk memastikan plot terupdate

def reset_data():
    """Reset all collected data"""
    global time_data, distance_data, start_time, update_needed, latest_analysis_text
    time_data.clear()
    distance_data.clear()
    start_time = None
    update_needed = True
    latest_analysis_text = ""  # PERBAIKAN: Reset hasil analisis juga
    
    data_count_label.config(text="Jumlah Data: 0")
    latest_data_label.config(text="Terbaru: -")
    status_label.config(text="Status: Data Direset", fg="blue")
    update_plot()
    update_analysis_display()  # PERBAIKAN: Update display analisis setelah reset
    print("Data dan hasil analisis telah direset.")

def update_data_table():
    """Update the data table with latest measurements"""
    global data_tree
    
    try:
        # Clear existing items
        for item in data_tree.get_children():
            data_tree.delete(item)
        
        # PERBAIKAN: Validasi data sebelum menampilkan
        if not time_data or not distance_data:
            return
        
        if len(time_data) != len(distance_data):
            print(f"Warning: Data length mismatch - time: {len(time_data)}, distance: {len(distance_data)}")
            return
        
        # Add latest 50 data points (or all if less than 50)
        start_idx = max(0, len(time_data) - 50)
        
        for i in range(start_idx, len(time_data)):
            try:
                # PERBAIKAN: Validasi setiap data point
                if i < len(time_data) and i < len(distance_data):
                    t = time_data[i]
                    d = distance_data[i]
                    
                    # Validasi tipe data
                    if isinstance(t, (int, float)) and isinstance(d, (int, float)):
                        if not (np.isnan(t) or np.isnan(d) or np.isinf(t) or np.isinf(d)):
                            raw_distance = sensor_height - d
                            
                            data_tree.insert('', 'end', values=(
                                i + 1,
                                f"{float(t):.2f}",
                                f"{float(d):.1f}",
                                f"{float(raw_distance):.1f}"
                            ))
                        else:
                            print(f"Skipping invalid data point {i}: NaN or Inf values")
                    else:
                        print(f"Skipping invalid data point {i}: wrong data type")
                        
            except Exception as e:
                print(f"Error processing data point {i}: {e}")
                continue
        
        # Scroll to bottom
        if data_tree.get_children():
            data_tree.see(data_tree.get_children()[-1])
            
    except Exception as e:
        print(f"Error updating data table: {e}")

def save_analysis_to_file():
    """Save analysis results to file"""
    global latest_analysis_text
    
    if not latest_analysis_text:
        messagebox.showwarning("Peringatan", "Tidak ada hasil analisis untuk disimpan.\nSilakan hitung koefisien restitusi terlebih dahulu.")
        return
    
    try:
        # Generate filename with ball type and timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ball_name = selected_ball_type.replace(" ", "_").replace("/", "_")  # PERBAIKAN: Hapus karakter invalid
        default_filename = f"Analisis_{ball_name}_{timestamp}.txt"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("File Teks", "*.txt"), ("File CSV", "*.csv"), ("Semua file", "*.*")],  # PERBAIKAN: Tambah format CSV
            title="Simpan Hasil Analisis",
            initialdir=os.getcwd(),
            initialfile=default_filename
        )
        
        if file_path:
            # PERBAIKAN: Validasi dan bersihkan teks analisis
            clean_analysis_text = latest_analysis_text
            
            # Ganti karakter yang bermasalah
            clean_analysis_text = clean_analysis_text.replace('\x00', '')  # Hapus null character
            clean_analysis_text = clean_analysis_text.replace('\r\n', '\n')  # Standardize line endings
            clean_analysis_text = clean_analysis_text.replace('\r', '\n')
            
            # PERBAIKAN: Tulis dengan encoding UTF-8 dan error handling
            with open(file_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(clean_analysis_text)
            
            messagebox.showinfo("Berhasil", f"Hasil analisis {selected_ball_type} disimpan ke {file_path}")
            
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menyimpan file analisis:\n{str(e)}")
        print(f"Analysis save error details: {e}")

def update_analysis_display():
    """Update the analysis display with current statistics"""
    global analysis_text, latest_analysis_text
    
    if len(distance_data) < 2:
        analysis_info = "Tidak ada data tersedia untuk analisis"
    else:
        # Check if we have detailed analysis results
        if latest_analysis_text:
            analysis_info = latest_analysis_text
        else:
            # Basic statistics jika belum ada analisis koefisien
            min_height = min(distance_data)
            max_height = max(distance_data)
            avg_height = np.mean(distance_data)
            std_height = np.std(distance_data)
            
            # Bounce detection
            bounce_times, bounce_distances = detect_bounces(distance_data, time_data)
            
            # Calculate coefficient if possible
            coefficients = []
            if len(bounce_distances) >= 2:
                for i in range(1, len(bounce_distances)):
                    if bounce_distances[i-1] > 0:
                        e = np.sqrt(bounce_distances[i] / bounce_distances[i-1])
                        coefficients.append(e)
            
            analysis_info = f"""ANALISIS REAL-TIME - {selected_ball_type.upper()}
{"="*30}

JENIS BOLA: {selected_ball_type}

STATISTIK DATA:
• Jumlah Data: {len(distance_data)}
• Durasi: {max(time_data) if time_data else 0:.1f}s
• Tinggi Min: {min_height:.1f} cm
• Tinggi Max: {max_height:.1f} cm
• Tinggi Rata-rata: {avg_height:.1f} cm
• Standar Deviasi: {std_height:.1f} cm

DETEKSI PANTULAN:
• Ambang Batas: {bounce_threshold:.1f} cm
• Pantulan Ditemukan: {len(bounce_distances)}
• Tinggi Pantulan: {[f"{h:.1f}" for h in bounce_distances[:5]]}{'...' if len(bounce_distances) > 5 else ''}

ANALISIS KOEFISIEN:
• Pasangan Valid: {len(coefficients)}
• Koefisien Rata-rata: {np.mean(coefficients):.3f if coefficients else 'N/A'}
• Retensi Energi: {np.mean(coefficients)**2*100 if coefficients else 0:.1f}%

PENGATURAN:
• Tinggi Sensor: {sensor_height:.1f} cm
• Jarak Min: {min_bounce_distance}
• Pengumpulan: {'Aktif' if collecting else 'Berhenti'}

CATATAN:
Klik "Hitung Koefisien Restitusi" untuk 
analisis lengkap dan detail perhitungan.
"""
    
    # Update analysis text widget
    analysis_text.config(state=tk.NORMAL)
    analysis_text.delete(1.0, tk.END)
    analysis_text.insert(1.0, analysis_info)
    analysis_text.config(state=tk.DISABLED)

def update_plot():
    """Update the matplotlib plot"""
    try:
        if len(time_data) == 0:
            ax.clear()
            ax.set_xlabel("Waktu (detik)")
            ax.set_ylabel("Tinggi Bola (cm)")
            ax.set_title(f"Pengukuran Tinggi {selected_ball_type} Real-time")
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
        ax.plot(time_data, filtered, 'b-', label=f"Tinggi {selected_ball_type}", linewidth=2)
        
        # Show bounces if enough data
        if len(filtered) > 20:
            bounce_times, bounce_distances = detect_bounces(filtered, time_data, 
                                                           bounce_threshold, min_bounce_distance)
            if bounce_times and bounce_distances:
                ax.plot(bounce_times, bounce_distances, "ro", label=f"Puncak Pantulan", markersize=8)
                
                # Add height annotations on peaks
                for i, (bt, bd) in enumerate(zip(bounce_times, bounce_distances)):
                    ax.annotate(f'{bd:.1f}', (bt, bd), 
                               textcoords="offset points", xytext=(0,10), ha='center',
                               fontsize=8, color='red', weight='bold')
        
        ax.set_xlabel("Waktu (detik)")
        ax.set_ylabel("Tinggi Bola (cm)")
        ax.set_title(f"Monitor Tinggi {selected_ball_type} (Sensor: {sensor_height}cm, Ambang: {bounce_threshold}cm)")
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Set axis limits
        if len(time_data) > 1:
            time_range = max(max(time_data) - min(time_data), 1)
            x_margin = time_range * 0.05
            ax.set_xlim(min(time_data) - x_margin, max(time_data) + x_margin)
        
        if len(filtered) > 1:
            dist_range = max(max(filtered) - min(filtered), 5)
            y_margin = dist_range * 0.1
            ax.set_ylim(max(0, min(filtered) - y_margin), max(filtered) + y_margin)
        
        canvas.draw_idle()
        
        # Update other displays
        update_data_table()
        update_analysis_display()
        
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
        interval = simpledialog.askinteger("Atur Interval", 
                                         "Masukkan interval dalam milidetik (50-5000):",
                                         initialvalue=100, minvalue=50, maxvalue=5000)
        if interval:
            send_mqtt_command(f"INTERVAL:{interval}")
    except Exception as e:
        print(f"Error setting interval: {e}")

def set_sensor_height():
    """Set sensor height from ground"""
    global sensor_height, update_needed
    try:
        new_height = simpledialog.askfloat("Atur Tinggi Sensor", 
                                         f"Masukkan tinggi sensor dari lantai (cm):\nSaat ini: {sensor_height}cm",
                                         initialvalue=sensor_height, minvalue=10, maxvalue=200)
        if new_height:
            sensor_height = new_height
            update_needed = True
            status_label.config(text=f"Status: Tinggi sensor diatur ke {sensor_height}cm", fg="blue")
            print(f"Tinggi sensor diubah ke: {sensor_height}cm")
    except Exception as e:
        print(f"Error setting sensor height: {e}")

def set_bounce_threshold():
    """Set bounce detection threshold"""
    global bounce_threshold, update_needed
    try:
        new_threshold = simpledialog.askfloat("Atur Ambang Pantulan", 
                                            f"Masukkan tinggi minimum pantulan (cm):\nSaat ini: {bounce_threshold}cm",
                                            initialvalue=bounce_threshold, minvalue=1.0, maxvalue=50.0)
        if new_threshold:
            bounce_threshold = new_threshold
            update_needed = True
            status_label.config(text=f"Status: Ambang pantulan diatur ke {bounce_threshold}cm", fg="blue")
            print(f"Ambang pantulan diubah ke: {bounce_threshold}cm")
    except Exception as e:
        print(f"Error setting bounce threshold: {e}")

def set_min_height_difference():
    """Set minimum height difference between consecutive peaks"""
    global min_height_difference, update_needed
    try:
        new_diff = simpledialog.askfloat("Atur Selisih Tinggi Minimum", 
                                       f"Masukkan selisih tinggi minimum antar puncak (cm):\nSaat ini: {min_height_difference}cm",
                                       initialvalue=min_height_difference, minvalue=0.1, maxvalue=10.0)
        if new_diff:
            min_height_difference = new_diff
            update_needed = True
            status_label.config(text=f"Status: Selisih tinggi minimum diatur ke {min_height_difference}cm", fg="blue")
            print(f"Selisih tinggi minimum diubah ke: {min_height_difference}cm")
    except Exception as e:
        print(f"Error setting min height difference: {e}")

def set_min_bounce_distance():
    """Set minimum distance between bounces"""
    global min_bounce_distance, update_needed
    try:
        new_distance = simpledialog.askinteger("Atur Jarak Minimum Pantulan", 
                                             f"Masukkan jarak minimum antar pantulan (titik data):\nSaat ini: {min_bounce_distance}",
                                             initialvalue=min_bounce_distance, minvalue=1, maxvalue=100)
        if new_distance:
            min_bounce_distance = new_distance
            update_needed = True
            status_label.config(text=f"Status: Jarak minimum pantulan diatur ke {min_bounce_distance}", fg="blue")
            print(f"Jarak minimum pantulan diubah ke: {min_bounce_distance}")
    except Exception as e:
        print(f"Error setting min bounce distance: {e}")

def save_excel():
    """Save collected data to an Excel file."""
    if not time_data or not distance_data:
        messagebox.showwarning("Peringatan", "Tidak ada data untuk disimpan.")
        return
    
    # PERBAIKAN: Validasi data sebelum menyimpan
    if len(time_data) != len(distance_data):
        messagebox.showerror("Error", f"Ketidakcocokan jumlah data:\nWaktu: {len(time_data)}\nJarak: {len(distance_data)}")
        return
    
    try:
        # Generate filename with ball type and timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ball_name = selected_ball_type.replace(" ", "_").replace("/", "_")  # PERBAIKAN: Hapus karakter invalid
        default_filename = f"Data_{ball_name}_{timestamp}.xlsx"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("File Excel", "*.xlsx")],
            title="Simpan Data ke Excel",
            initialdir=os.getcwd(),  # PERBAIKAN: Simpan di direktori kerja saat ini
            initialfile=default_filename
        )
        
        if file_path:
            # PERBAIKAN: Validasi dan bersihkan data
            clean_time_data = []
            clean_distance_data = []
            clean_sensor_heights = []
            clean_ball_types = []
            
            for i, (t, d) in enumerate(zip(time_data, distance_data)):
                # Validasi setiap data point
                if isinstance(t, (int, float)) and isinstance(d, (int, float)):
                    if not (np.isnan(t) or np.isnan(d) or np.isinf(t) or np.isinf(d)):
                        clean_time_data.append(float(t))
                        clean_distance_data.append(float(d))
                        clean_sensor_heights.append(float(sensor_height))
                        clean_ball_types.append(str(selected_ball_type))
                    else:
                        print(f"Data point {i} diabaikan: nilai tidak valid (NaN/Inf)")
                else:
                    print(f"Data point {i} diabaikan: tipe data tidak valid")
            
            if not clean_time_data:
                messagebox.showerror("Error", "Tidak ada data valid untuk disimpan.")
                return
            
            # PERBAIKAN: Buat DataFrame dengan data yang sudah dibersihkan
            df = pd.DataFrame({
                "Waktu (detik)": clean_time_data, 
                f"Tinggi {selected_ball_type} (cm)": clean_distance_data,
                "Tinggi Sensor (cm)": clean_sensor_heights,
                "Jenis Bola": clean_ball_types
            })
            
            # PERBAIKAN: Validasi DataFrame sebelum menyimpan
            if df.empty:
                messagebox.showerror("Error", "DataFrame kosong, tidak dapat menyimpan.")
                return
            
            df.to_excel(file_path, index=False, engine='openpyxl')
            messagebox.showinfo("Berhasil", f"Data {selected_ball_type} disimpan ke {file_path}\nTotal data valid: {len(clean_time_data)}")
            
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menyimpan data ke Excel:\n{str(e)}\n\nPastikan file tidak sedang dibuka di aplikasi lain.")
        print(f"Excel save error details: {e}")

def save_png():
    """Save the current plot as a PNG file."""
    try:
        # PERBAIKAN: Validasi plot sebelum menyimpan
        if fig is None or ax is None:
            messagebox.showerror("Error", "Grafik belum tersedia untuk disimpan.")
            return
        
        # Generate filename with ball type and timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ball_name = selected_ball_type.replace(" ", "_").replace("/", "_")  # PERBAIKAN: Hapus karakter invalid
        default_filename = f"Grafik_{ball_name}_{timestamp}.png"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png", 
            filetypes=[("File PNG", "*.png"), ("File JPG", "*.jpg"), ("File PDF", "*.pdf")],  # PERBAIKAN: Tambah format lain
            title="Simpan Grafik",
            initialdir=os.getcwd(),  # PERBAIKAN: Simpan di direktori kerja saat ini
            initialfile=default_filename
        )
        
        if file_path:
            # PERBAIKAN: Update plot sebelum menyimpan
            update_plot()
            
            # PERBAIKAN: Simpan dengan parameter yang lebih aman
            fig.savefig(file_path, 
                       dpi=300, 
                       bbox_inches='tight',
                       facecolor='white',  # PERBAIKAN: Background putih
                       edgecolor='none',   # PERBAIKAN: Tanpa border
                       format=None)        # PERBAIKAN: Auto-detect format
            
            messagebox.showinfo("Berhasil", f"Grafik {selected_ball_type} disimpan ke {file_path}")
            
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menyimpan grafik:\n{str(e)}")
        print(f"PNG save error details: {e}")

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

def refresh_plot_manually():
    """Manually refresh the plot."""
    update_plot()

def setup_gui():
    """Initialize GUI components with improved 2-row layout"""
    global root, fig, ax, canvas, status_label, data_count_label, latest_data_label
    global data_tree, analysis_text
    
    root = tk.Tk()
    root.title(f"Monitor Tinggi Bola HC-SR04 - {selected_ball_type}")
    root.protocol("WM_DELETE_WINDOW", close_app)
    
    # Set fullscreen
    root.state('zoomed')  # Windows fullscreen
    # Alternative for other OS: root.attributes('-zoomed', True)
    
    # Configure grid weights for responsive design
    root.grid_rowconfigure(0, weight=1)  # Main content row
    root.grid_rowconfigure(1, weight=0)  # Control buttons row
    root.grid_columnconfigure(0, weight=1)
    
    # ===========================================
    # BARIS 1: KONTEN UTAMA (3 KOLOM)
    # ===========================================
    main_frame = tk.Frame(root, relief=tk.RAISED, bd=1)
    main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    
    # Configure main frame grid
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=2)  # Plot gets more space
    main_frame.grid_columnconfigure(1, weight=1)  # Data table
    main_frame.grid_columnconfigure(2, weight=1)  # Analysis
    
    # -------------------------------------------
    # KOLOM 1: BAGIAN GRAFIK
    # -------------------------------------------
    plot_frame = tk.LabelFrame(main_frame, text=f"Grafik Real-time - {selected_ball_type}", font=("Arial", 12, "bold"))
    plot_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    
    # Setup matplotlib
    fig = Figure(figsize=(10, 8), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlabel("Waktu (detik)")
    ax.set_ylabel("Tinggi Bola (cm)")
    ax.set_title(f"Pengukuran Tinggi {selected_ball_type} Real-time")
    ax.grid(True, alpha=0.3)
    
    canvas = FigureCanvasTkAgg(fig, master=plot_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # -------------------------------------------
    # KOLOM 2: BAGIAN TABEL DATA
    # -------------------------------------------
    table_frame = tk.LabelFrame(main_frame, text="Tabel Data (50 Terakhir)", font=("Arial", 12, "bold"))
    table_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    
    # Create treeview for data table
    table_container = tk.Frame(table_frame)
    table_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Scrollbars for table
    v_scrollbar = tk.Scrollbar(table_container, orient="vertical")
    h_scrollbar = tk.Scrollbar(table_container, orient="horizontal")
    
    # Data table
    columns = ('Indeks', 'Waktu (s)', 'Tinggi (cm)', 'Jarak Mentah (cm)')
    data_tree = ttk.Treeview(table_container, columns=columns, show='headings',
                            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Configure columns
    data_tree.heading('Indeks', text='#')
    data_tree.heading('Waktu (s)', text='Waktu (s)')
    data_tree.heading('Tinggi (cm)', text='Tinggi (cm)')
    data_tree.heading('Jarak Mentah (cm)', text='Jarak Mentah (cm)')
    
    data_tree.column('Indeks', width=60)
    data_tree.column('Waktu (s)', width=90)
    data_tree.column('Tinggi (cm)', width=100)
    data_tree.column('Jarak Mentah (cm)', width=120)
    
    # Pack table and scrollbars
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar.pack(side="bottom", fill="x")
    data_tree.pack(side="left", fill="both", expand=True)
    
    v_scrollbar.config(command=data_tree.yview)
    h_scrollbar.config(command=data_tree.xview)
    
    # -------------------------------------------
    # KOLOM 3: BAGIAN ANALISIS
    # -------------------------------------------
    analysis_frame = tk.LabelFrame(main_frame, text=f"Analisis Real-time & Hasil Koefisien - {selected_ball_type}", font=("Arial", 12, "bold"))
    analysis_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
    
    # Analysis text widget with scrollbar
    analysis_container = tk.Frame(analysis_frame)
    analysis_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    analysis_scrollbar = tk.Scrollbar(analysis_container)
    analysis_scrollbar.pack(side="right", fill="y")
    
    analysis_text = tk.Text(analysis_container, yscrollcommand=analysis_scrollbar.set,
                           font=("Courier", 9), wrap=tk.WORD, state=tk.DISABLED)
    analysis_text.pack(side="left", fill="both", expand=True)
    analysis_scrollbar.config(command=analysis_text.yview)
    
    # ===========================================
    # BARIS 2: TOMBOL KONTROL (BEBERAPA BARIS)
    # ===========================================
    control_frame = tk.Frame(root, relief=tk.RAISED, bd=1)
    control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
    
    # Status row
    status_frame = tk.Frame(control_frame)
    status_frame.pack(fill=tk.X, padx=5, pady=2)
    
    status_label = tk.Label(status_frame, text="Status: Berhenti", font=("Arial", 14, "bold"))
    status_label.pack(side=tk.LEFT)
    
    latest_data_label = tk.Label(status_frame, text="Terbaru: -", font=("Arial", 12))
    latest_data_label.pack(side=tk.LEFT, padx=20)
    
    data_count_label = tk.Label(status_frame, text="Jumlah Data: 0", font=("Arial", 12))
    data_count_label.pack(side=tk.RIGHT)
    
    # Configuration row
    config_frame = tk.LabelFrame(control_frame, text="Konfigurasi", font=("Arial", 11, "bold"))
    config_frame.pack(fill=tk.X, padx=5, pady=3)
    
    tk.Button(config_frame, text=f"Jenis Bola: {selected_ball_type}", 
             command=set_ball_type, bg="lightblue", width=20, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(config_frame, text=f"Tinggi Sensor: {sensor_height}cm", 
             command=set_sensor_height, bg="lightgray", width=18, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(config_frame, text=f"Ambang Pantulan: {bounce_threshold}cm", 
             command=set_bounce_threshold, bg="lightyellow", width=20, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    
    # Configuration row 2 - PERBAIKAN: Tambah tombol untuk selisih tinggi minimum
    config_frame2 = tk.LabelFrame(control_frame, text="Konfigurasi Lanjutan", font=("Arial", 11, "bold"))
    config_frame2.pack(fill=tk.X, padx=5, pady=3)
    
    tk.Button(config_frame2, text=f"Selisih Tinggi Min: {min_height_difference}cm", 
             command=set_min_height_difference, bg="lightpink", width=20, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(config_frame2, text=f"Jarak Min: {min_bounce_distance}", 
             command=set_min_bounce_distance, bg="lightcyan", width=15, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    
    # Main control row
    main_control_frame = tk.LabelFrame(control_frame, text="Kontrol Utama", font=("Arial", 11, "bold"))
    main_control_frame.pack(fill=tk.X, padx=5, pady=3)
    
    tk.Button(main_control_frame, text="Mulai Pengumpulan", command=start_collection, 
             bg="lightgreen", width=15, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(main_control_frame, text="Hentikan Pengumpulan", command=stop_collection, 
             bg="lightcoral", width=18, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(main_control_frame, text="Reset Data", command=reset_data, 
             bg="lightyellow", width=12, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(main_control_frame, text="Refresh Grafik", command=refresh_plot_manually, 
             bg="lightcyan", width=12, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    
    # Analysis and export row
    analysis_control_frame = tk.LabelFrame(control_frame, text="Analisis & Ekspor", font=("Arial", 11, "bold"))
    analysis_control_frame.pack(fill=tk.X, padx=5, pady=3)
    
    tk.Button(analysis_control_frame, text="Hitung Koefisien Restitusi", command=calculate_restitution_coefficient, 
             bg="orange", width=20, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(analysis_control_frame, text="Simpan Hasil Analisis", command=save_analysis_to_file, 
             bg="lightgreen", width=15, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(analysis_control_frame, text="Simpan Data (Excel)", command=save_excel, 
             bg="lightblue", width=15, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(analysis_control_frame, text="Simpan Grafik (PNG)", command=save_png, 
             bg="lightblue", width=15, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    
    # ESP control row
    esp_control_frame = tk.LabelFrame(control_frame, text="Kontrol ESP8266/ESP32", font=("Arial", 11, "bold"))
    esp_control_frame.pack(fill=tk.X, padx=5, pady=3)
    
    tk.Button(esp_control_frame, text="Mulai Pembacaan ESP", command=lambda: send_mqtt_command("START_READING"), 
             bg="lightgreen", width=18, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(esp_control_frame, text="Hentikan Pembacaan ESP", command=lambda: send_mqtt_command("STOP_READING"), 
             bg="lightcoral", width=20, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(esp_control_frame, text="Minta Jarak", command=lambda: send_mqtt_command("READ_DISTANCE"), 
             bg="lightyellow", width=12, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    tk.Button(esp_control_frame, text="Atur Interval", command=set_interval, 
             bg="lightcyan", width=12, font=("Arial", 10)).pack(side=tk.LEFT, padx=3, pady=3)
    
    # Exit button
    tk.Button(esp_control_frame, text="Keluar Aplikasi", command=close_app, 
             bg="lightgray", width=15, font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=3, pady=3)
    
    # Initialize displays
    update_analysis_display()

def main():
    """Main application entry point"""
    print("=== Monitor Tinggi Bola HC-SR04 ===")
    print("Kompatibel dengan ESP8266 dan ESP32")
    print(f"MQTT Broker: {MQTT_BROKER}")
    print(f"MQTT Topic: {MQTT_TOPIC}")
    print(f"Tinggi Sensor: {sensor_height}cm")
    print("=====================================")
    
    # Setup GUI
    setup_gui()
    
    # Setup MQTT
    setup_mqtt()
    
    # Start periodic updates
    root.after(100, periodic_update)
    
    print("Aplikasi dimulai!")
    print("- Klik 'Mulai' untuk memulai pengumpulan data")
    print("- Atur tinggi sensor sebelum pengukuran")
    print("- Perangkat ESP harus mempublikasikan ke topik:", MQTT_TOPIC)
    
    # Start GUI main loop
    root.mainloop()

if __name__ == "__main__":
    main()