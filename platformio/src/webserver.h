#ifndef WEBSERVER_H
#define WEBSERVER_H

#ifdef ESP32
  #include <WebServer.h>
  extern WebServer server;
#elif defined(ESP8266)
  #include <ESP8266WebServer.h>
  extern ESP8266WebServer server;
#endif

#include <vector>

// External variables from main.cpp
extern std::vector<String> sensorData;
extern bool isReading;
extern unsigned long startTime;
extern String currentExperiment;
extern unsigned long sensorInterval;

void handleRoot() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <title>HC-SR04 Data Logger</title>
    <meta charset='UTF-8'>
    <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
    <style>
        body { font-family: Arial; margin: 20px; }
        .container { display: flex; flex-wrap: wrap; gap: 20px; }
        .controls { flex: 1; min-width: 300px; }
        .chart-container { flex: 2; min-width: 400px; }
        button { padding: 10px 15px; margin: 5px; font-size: 14px; border: none; cursor: pointer; }
        .start { background-color: #4CAF50; color: white; }
        .stop { background-color: #f44336; color: white; }
        .download { background-color: #008CBA; color: white; }
        input[type="text"] { padding: 8px; margin: 5px; width: 200px; }
        input[type="number"] { padding: 8px; margin: 5px; width: 100px; }
        #dataTable { width: 100%; border-collapse: collapse; margin-top: 10px; }
        #dataTable th, #dataTable td { border: 1px solid #ddd; padding: 5px; text-align: center; }
        #dataTable th { background-color: #f2f2f2; }
        .status { font-weight: bold; color: #333; }
    </style>
</head>
<body>
    <h1>HC-SR04 Data Logger - Real Time</h1>
    
    <div class="container">
        <div class="controls">
            <div>
                <label>Nama Percobaan:</label><br>
                <input type="text" id="experimentName" value="Percobaan 1" placeholder="Nama percobaan">
                <button onclick="updateExperiment()">Set</button>
            </div>
            
            <div>
                <label>Interval Sampling (ms):</label><br>
                <input type="number" id="samplingInterval" value="50" min="10" max="1000">
                <button onclick="updateInterval()">Set</button>
            </div>
            
            <div>
                <p class="status">Status: <span id="status">BERHENTI</span></p>
                <p class="status">Total Data: <span id="dataCount">0</span></p>
                <p class="status">Percobaan: <span id="currentExp">Percobaan 1</span></p>
            </div>
            
            <div>
                <button class="start" onclick="startReading()">START</button>
                <button class="stop" onclick="stopReading()">STOP</button>
                <button class="download" onclick="downloadCSV()">DOWNLOAD CSV</button>
                <button onclick="clearData()">CLEAR DATA</button>
                <button onclick="showAllData()">SHOW ALL DATA</button>
            </div>
        </div>
        
        <div class="chart-container">
            <canvas id="distanceChart" width="400" height="200"></canvas>
        </div>
    </div>
    
    <h3>Data Real-time (10 terakhir):</h3>
    <table id="dataTable">
        <thead>
            <tr><th>Waktu (s)</th><th>Jarak (cm)</th><th>Percobaan</th></tr>
        </thead>
        <tbody id="dataTableBody">
        </tbody>
    </table>

    <script>
        const ws = new WebSocket('ws://' + window.location.hostname + ':81');
        let chart;
        let allDataPoints = []; // Store all data points
        let realtimeDataPoints = []; // For real-time display
        let maxRealtimePoints = 100;
        let showingAllData = false;

        // Initialize Chart
        const ctx = document.getElementById('distanceChart').getContext('2d');
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Jarak (cm)',
                    data: realtimeDataPoints,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: { 
                        type: 'linear',
                        title: { display: true, text: 'Waktu (s)' }
                    },
                    y: { 
                        title: { display: true, text: 'Jarak (cm)' }
                    }
                },
                animation: false
            }
        });

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            // Store all data points
            allDataPoints.push({x: data.timestamp, y: data.distance});
            
            // Update chart based on current view mode
            if (showingAllData) {
                // If showing all data, update the chart with complete dataset
                chart.data.datasets[0].data = allDataPoints;
                chart.update('none');
                // Also update the table with all data
                updateAllDataTable();
            } else {
                // Real-time mode - rolling window
                realtimeDataPoints.push({x: data.timestamp, y: data.distance});
                if (realtimeDataPoints.length > maxRealtimePoints) {
                    realtimeDataPoints.shift();
                }
                chart.data.datasets[0].data = realtimeDataPoints;
                chart.update('none');
                // Update table with latest 10 entries
                updateTable(data);
            }
            
            // Update counters
            updateStatus();
        };

        function updateTable(data) {
            const tbody = document.getElementById('dataTableBody');
            const row = tbody.insertRow(0);
            row.innerHTML = `<td>${data.timestamp.toFixed(3)}</td><td>${data.distance}</td><td>${data.experiment}</td>`;
            
            // Keep only last 10 rows
            while (tbody.rows.length > 10) {
                tbody.deleteRow(-1);
            }
        }

        function updateAllDataTable() {
            const tbody = document.getElementById('dataTableBody');
            tbody.innerHTML = ''; // Clear existing rows
            
            // Show last 20 data points when showing all data (or all if less than 20)
            const displayCount = Math.min(20, allDataPoints.length);
            const startIndex = Math.max(0, allDataPoints.length - displayCount);
            
            for (let i = allDataPoints.length - 1; i >= startIndex; i--) {
                const row = tbody.insertRow(-1);
                const point = allDataPoints[i];
                // Extract experiment name from the last data entry (assuming consistent experiment)
                const experiment = document.getElementById('currentExp').textContent;
                row.innerHTML = `<td>${point.x.toFixed(3)}</td><td>${point.y}</td><td>${experiment}</td>`;
            }
        }

        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').textContent = data.isReading ? 'MEMBACA DATA' : 'BERHENTI';
                    document.getElementById('dataCount').textContent = data.dataCount;
                    document.getElementById('currentExp').textContent = data.currentExperiment;
                });
        }

        function startReading() {
            fetch('/start', {method: 'POST'});
            allDataPoints = []; // Clear all data when starting new measurement
            realtimeDataPoints = [];
            showingAllData = false;
            chart.data.datasets[0].data = realtimeDataPoints;
            chart.update();
        }

        function stopReading() {
            fetch('/stop', {method: 'POST'});
        }

        function downloadCSV() {
            window.open('/download', '_blank');
        }

        function clearData() {
            fetch('/clear', {method: 'POST'});
            allDataPoints = [];
            realtimeDataPoints = [];
            showingAllData = false;
            chart.data.datasets[0].data = realtimeDataPoints;
            chart.data.datasets[0].label = 'Jarak (cm)';
            chart.update();
            document.getElementById('dataTableBody').innerHTML = '';
        }

        function showAllData() {
            showingAllData = !showingAllData;
            const button = document.querySelector('button[onclick="showAllData()"]');
            const tableHeader = document.querySelector('h3');
            
            if (showingAllData) {
                chart.data.datasets[0].data = allDataPoints;
                chart.data.datasets[0].label = 'Jarak (cm) - Semua Data';
                button.textContent = 'SHOW REALTIME';
                tableHeader.textContent = 'Data Lengkap (20 terakhir):';
                updateAllDataTable();
            } else {
                chart.data.datasets[0].data = realtimeDataPoints;
                chart.data.datasets[0].label = 'Jarak (cm) - Real-time';
                button.textContent = 'SHOW ALL DATA';
                tableHeader.textContent = 'Data Real-time (10 terakhir):';
                // Clear and rebuild real-time table
                document.getElementById('dataTableBody').innerHTML = '';
            }
            chart.update();
        }

        function updateExperiment() {
            const name = document.getElementById('experimentName').value;
            fetch('/setExperiment', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'name=' + encodeURIComponent(name)
            });
        }

        function updateInterval() {
            const interval = document.getElementById('samplingInterval').value;
            fetch('/setInterval', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'interval=' + interval
            });
        }

        // Update status every 2 seconds
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
)rawliteral";
  
  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\"isReading\":" + String(isReading ? "true" : "false") + ",";
  json += "\"dataCount\":" + String(sensorData.size()) + ",";
  json += "\"currentExperiment\":\"" + currentExperiment + "\"";
  json += "}";
  server.send(200, "application/json", json);
}

void handleSetExperiment() {
  if (server.hasArg("name")) {
    currentExperiment = server.arg("name");
    server.send(200, "text/plain", "Experiment name updated");
  } else {
    server.send(400, "text/plain", "Missing name parameter");
  }
}

void handleSetInterval() {
  if (server.hasArg("interval")) {
    sensorInterval = server.arg("interval").toInt();
    if (sensorInterval < 10) sensorInterval = 10;
    if (sensorInterval > 1000) sensorInterval = 1000;
    server.send(200, "text/plain", "Interval updated");
  } else {
    server.send(400, "text/plain", "Missing interval parameter");
  }
}

void handleStart() {
  isReading = true;
  startTime = millis();
  sensorData.clear();
  server.send(200, "text/plain", "Data reading started");
}

void handleStop() {
  isReading = false;
  server.send(200, "text/plain", "Data reading stopped");
}

void handleDownload() {
  String filename = currentExperiment;
  filename.replace(" ", "_");
  filename.replace("/", "_");
  filename.replace("\\", "_");
  filename += ".csv";
  
  String csv = "Timestamp(s),Distance(cm),Unit,Experiment\n";
  for(String data : sensorData) {
    csv += data + "\n";
  }
  
  server.sendHeader("Content-Disposition", "attachment; filename=\"" + filename + "\"");
  server.send(200, "text/csv", csv);
}

void handleClear() {
  sensorData.clear();
  server.send(200, "text/plain", "Data cleared");
}

void setupWebServer() {
  server.on("/", handleRoot);
  server.on("/start", HTTP_POST, handleStart);
  server.on("/stop", HTTP_POST, handleStop);
  server.on("/download", handleDownload);
  server.on("/clear", HTTP_POST, handleClear);
  server.on("/status", handleStatus);
  server.on("/setExperiment", HTTP_POST, handleSetExperiment);
  server.on("/setInterval", HTTP_POST, handleSetInterval);
  server.begin();
  
  Serial.println("Web server started");
  Serial.print("Access at: http://");
  Serial.println(WiFi.localIP());
  Serial.print("WebSocket server at: ws://");
  Serial.print(WiFi.localIP());
  Serial.println(":81");
}

#endif
