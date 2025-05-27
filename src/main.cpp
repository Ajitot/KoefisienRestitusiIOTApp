#ifdef ESP32
  #include <WiFi.h>
  #define LED_BUILTIN 2
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
#endif

#include <PubSubClient.h>
#include <ArduinoJson.h>  // Tambahkan untuk JSON yang proper

// Update these with values suitable for your network.
const char* ssid = "Al muajir";
const char* password = "1618199923";

// **MQTT Broker Cloud**
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;

const char* mqtt_topic = "sensor/distance";
const char* mqtt_cmd_topic = "sensor/distance/cmd";  // Tambah topik untuk command

// HC-SR04 sensor pins
#ifdef ESP32
  #define TRIG_PIN 14
  #define ECHO_PIN 27
#elif defined(ESP8266)
  #define TRIG_PIN D1
  #define ECHO_PIN D2
#endif

WiFiClient espClient;
PubSubClient client(espClient);
unsigned long lastSensorRead = 0;
unsigned long lastMqttReconnect = 0;
unsigned long lastWifiCheck = 0;
unsigned long program_start_time = 0;  // Tambah untuk timestamp

bool isReading = false;
unsigned long sensorInterval = 100; // PERBAIKAN: Ubah ke 100ms untuk realtime

// Improved HC-SR04 reading dengan filtering
long readDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // Timeout 30ms
  if (duration == 0) return -1; // Timeout
  
  long distance = duration * 0.034 / 2;
  
  // Filter invalid readings
  if (distance < 2 || distance > 400) return -1;
  
  return distance;
}

void setup_wifi() {
  delay(10);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  randomSeed(micros());
  
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void checkWifiConnection() {
  unsigned long now = millis();
  if (now - lastWifiCheck > 10000) {
    lastWifiCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi disconnected, reconnecting...");
      WiFi.begin(ssid, password);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
    Serial.print((char)payload[i]);
  }
  Serial.println();

  // Handle commands
  if (message == "READ_DISTANCE") {
    long distance = readDistance();
    if (distance > 0) {
      // PERBAIKAN: Kirim dengan format JSON yang proper
      JsonDocument doc;
      doc["timestamp"] = (millis() - program_start_time) / 1000.0;
      doc["distance"] = distance;
      doc["device"] = "ESP8266_HCSR04";
      doc["command_response"] = true;
      
      String jsonString;
      serializeJson(doc, jsonString);
      client.publish(mqtt_topic, jsonString.c_str());
    }
  }
  else if (message == "START_READING") {
    isReading = true;
    Serial.println("Started continuous reading");
  }
  else if (message == "STOP_READING") {
    isReading = false;
    Serial.println("Stopped continuous reading");
  }
  else if (message.startsWith("INTERVAL:")) {
    // Command untuk ubah interval: "INTERVAL:100"
    int newInterval = message.substring(9).toInt();
    if (newInterval >= 50 && newInterval <= 5000) {
      sensorInterval = newInterval;
      Serial.println("Interval changed to: " + String(newInterval) + "ms");
    }
  }
  else if ((char)payload[0] == '1') {
    digitalWrite(LED_BUILTIN, LOW);
  } else {
    digitalWrite(LED_BUILTIN, HIGH);
  }
}

void reconnectMQTT() {
  unsigned long now = millis();
  if (!client.connected() && (now - lastMqttReconnect > 5000)) {
    lastMqttReconnect = now;
    Serial.print("Attempting MQTT connection...");
    
    #ifdef ESP32
      String clientId = "ESP32Client-";
    #elif defined(ESP8266)
      String clientId = "ESP8266Client-";
    #endif
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      
      // PERBAIKAN: Send connection message dengan JSON
      JsonDocument doc;
      doc["timestamp"] = (millis() - program_start_time) / 1000.0;
      doc["message"] = "Device connected";
      doc["device"] = clientId;
      doc["status"] = "online";
      
      String jsonString;
      serializeJson(doc, jsonString);
      client.publish(mqtt_topic, jsonString.c_str());
      
      // Subscribe ke kedua topik: data dan command
      client.subscribe(mqtt_topic);
      client.subscribe(mqtt_cmd_topic);
      Serial.println("Subscribed to data and command topics");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
    }
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.begin(115200);
  
  // PERBAIKAN: Catat waktu mulai program
  program_start_time = millis();
  
  setup_wifi();
  
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  
  Serial.println("System initialized");
  Serial.println("Program start time: " + String(program_start_time));
}

void loop() {
  client.loop();
  
  checkWifiConnection();
  reconnectMQTT();
  
  unsigned long now = millis();
  
  // PERBAIKAN: Sensor reading dengan JSON proper
  if (isReading && (now - lastSensorRead >= sensorInterval)) {
    lastSensorRead = now;
    
    long distance = readDistance();
    
    if (distance > 0 && client.connected()) {
      // PERBAIKAN: Format JSON yang sesuai dengan Python
      JsonDocument doc;
      doc["timestamp"] = (now - program_start_time) / 1000.0;
      doc["distance"] = distance;
      doc["device"] = "ESP8266_HCSR04";
      doc["uptime"] = now;
      
      String jsonString;
      serializeJson(doc, jsonString);
      
      if (client.publish(mqtt_topic, jsonString.c_str())) {
        Serial.println("Published: " + jsonString);
      } else {
        Serial.println("Failed to publish");
      }
    } else if (distance <= 0) {
      Serial.println("Invalid distance reading");
    }
  }
  
  yield();
}