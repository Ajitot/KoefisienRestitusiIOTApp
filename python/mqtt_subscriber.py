import paho.mqtt.client as mqtt
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

class HC_SR04_Subscriber:
    def __init__(self, broker="broker.mqtt-dashboard.com", topic="esp8266/hcsr04"):
        self.broker = broker
        self.topic = topic
        self.client = mqtt.Client()
        self.data = []
        self.is_collecting = False
        
        # Setup MQTT callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        if self.is_collecting:
            try:
                payload = json.loads(msg.payload.decode())
                if 'distance' in payload and 'timestamp' in payload:
                    self.data.append({
                        'timestamp': payload['timestamp'],
                        'distance': payload['distance'],
                        'experiment': payload.get('experiment', 'Unknown'),
                        'received_at': datetime.now()
                    })
                    print(f"Data received: {payload['distance']} cm at {payload['timestamp']} s")
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {msg.payload.decode()}")
                
    def start_collecting(self):
        self.is_collecting = True
        self.data.clear()
        print("Started data collection")
        
    def stop_collecting(self):
        self.is_collecting = False
        print(f"Stopped data collection. Collected {len(self.data)} data points")
        
    def connect(self):
        self.client.connect(self.broker, 1883, 60)
        self.client.loop_start()
        
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        
    def save_to_csv(self, filename=None):
        if not self.data:
            print("No data to save")
            return
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hcsr04_data_{timestamp}.csv"
            
        df = pd.DataFrame(self.data)
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")
        
    def plot_data(self):
        if not self.data:
            print("No data to plot")
            return
            
        df = pd.DataFrame(self.data)
        
        plt.figure(figsize=(12, 6))
        plt.plot(df['timestamp'], df['distance'], 'b-', linewidth=1, alpha=0.7)
        plt.xlabel('Time (s)')
        plt.ylabel('Distance (cm)')
        plt.title(f'HC-SR04 Distance Measurement - {df["experiment"].iloc[0]}')
        plt.grid(True, alpha=0.3)
        plt.show()
        
    def analyze_bouncing_ball(self, height_threshold=None):
        """Analyze bouncing ball data to calculate coefficient of restitution"""
        if not self.data:
            print("No data to analyze")
            return
            
        df = pd.DataFrame(self.data)
        distances = df['distance'].values
        timestamps = df['timestamp'].values
        
        # Find peaks (maximum heights during bounces)
        from scipy.signal import find_peaks
        
        # Invert distance data to find peaks (ball at maximum height = minimum distance to ground)
        inverted_distances = max(distances) - distances
        peaks, _ = find_peaks(inverted_distances, height=height_threshold, distance=50)
        
        if len(peaks) < 2:
            print("Not enough peaks found for coefficient calculation")
            return
            
        peak_heights = distances[peaks]
        peak_times = timestamps[peaks]
        
        print(f"Found {len(peaks)} bounces:")
        for i, (time, height) in enumerate(zip(peak_times, peak_heights)):
            print(f"Bounce {i+1}: {height:.1f} cm at {time:.3f} s")
            
        # Calculate coefficient of restitution between consecutive bounces
        coefficients = []
        for i in range(len(peak_heights) - 1):
            h1 = peak_heights[i]
            h2 = peak_heights[i + 1]
            e = np.sqrt(h2 / h1) if h1 > 0 else 0
            coefficients.append(e)
            print(f"Coefficient between bounce {i+1} and {i+2}: {e:.3f}")
            
        avg_coefficient = np.mean(coefficients)
        print(f"Average coefficient of restitution: {avg_coefficient:.3f}")
        
        return {
            'peaks': peaks,
            'peak_heights': peak_heights,
            'peak_times': peak_times,
            'coefficients': coefficients,
            'average_coefficient': avg_coefficient
        }

if __name__ == "__main__":
    # Example usage
    subscriber = HC_SR04_Subscriber()
    subscriber.connect()
    
    try:
        input("Press Enter to start collecting data...")
        subscriber.start_collecting()
        
        input("Press Enter to stop collecting data...")
        subscriber.stop_collecting()
        
        # Save and analyze data
        subscriber.save_to_csv()
        subscriber.plot_data()
        subscriber.analyze_bouncing_ball()
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        subscriber.disconnect()
