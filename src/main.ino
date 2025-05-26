#ifdef ESP32
  #include <WiFi.h>
  #include <WebServer.h>
  #include <WebSocketsServer.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266WebServer.h>
  #include <WebSocketsServer.h>
#endif

#include <PubSubClient.h>
#include <vector>
#include <ArduinoJson.h>
#include "webserver.h"

// Update these with values suitable for your network.

const char* ssid = "Al muajir";
const char* password = "1618199923";
// **MQTT Broker Cloud**
const char* mqtt_server = "broker.mqtt-dashboard.com";
// **MQTT Broker Local**
const int mqtt_port = 1883;

#ifdef ESP32
  const char* mqtt_topic = "esp32/hcsr04";
  WebServer server(80);
#elif defined(ESP8266)
  const char* mqtt_topic = "esp8266/hcsr04";
  ESP8266WebServer server(80);
#endif

WebSocketsServer webSocket = WebSocketsServer(81);

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
#define MSG_BUFFER_SIZE	(100)
char msg[MSG_BUFFER_SIZE];

// Data storage and control variables
std::vector<String> sensorData;
bool isReading = false;
unsigned long startTime = 0;
String currentExperiment = "Percobaan 1";
unsigned long sensorInterval = 50; // 50ms = 20Hz sampling rate

// Non-blocking HC-SR04 functions
long readDistanceNonBlocking() {
  static unsigned long triggerTime = 0;
  static bool triggerSent = false;
  static unsigned long pulseStart = 0;
  static bool pulseStarted = false;
  
  if (!triggerSent) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    triggerSent = true;
    triggerTime = micros();
    pulseStarted = false;
    return -1; // Not ready yet
  }
  
  if (digitalRead(ECHO_PIN) == HIGH && !pulseStarted) {
    pulseStart = micros();
    pulseStarted = true;
    return -1; // Still measuring
  }
  
  if (digitalRead(ECHO_PIN) == LOW && pulseStarted) {
    unsigned long duration = micros() - pulseStart;
    long distance = duration * 0.034 / 2;
    triggerSent = false; // Reset for next measurement
    return distance;
  }
  
  // Timeout after 30ms
  if (micros() - triggerTime > 30000) {
    triggerSent = false;
    return 0; // Timeout
  }
  
  return -1; // Still waiting
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
  if (now - lastWifiCheck > 10000) { // Check every 10 seconds
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
  
  // Convert payload to string
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
    Serial.print((char)payload[i]);
  }
  Serial.println();

  // Handle commands
  if (message == "READ_DISTANCE") {
    long distance = readDistanceNonBlocking();
    if (distance >= 0) {
      snprintf(msg, MSG_BUFFER_SIZE, "Distance: %ld cm", distance);
      client.publish(mqtt_topic, msg);
      Serial.println("Distance reading requested and sent");
    }
  }
  // Switch on the LED if an 1 was received as first character
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
    String clientId = "ESP8266Client-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      client.publish(mqtt_topic, "Device connected");
      client.subscribe(mqtt_topic);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
    }
  }
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("[%u] Disconnected!\n", num);
      break;
    case WStype_CONNECTED:
      Serial.printf("[%u] Connected from IP: %s\n", num, webSocket.remoteIP(num).toString().c_str());
      break;
    case WStype_TEXT:
      Serial.printf("[%u] Received: %s\n", num, payload);
      break;
    case WStype_FRAGMENT_TEXT_START:
    case WStype_FRAGMENT_BIN_START:
    case WStype_FRAGMENT:
    case WStype_FRAGMENT_FIN:
    case WStype_BIN:
    case WStype_ERROR:
    case WStype_PING:
    case WStype_PONG:
      // Handle other cases silently
      break;
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.begin(115200);
  
  // Wait for WiFi connection first
  setup_wifi();
  
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  
  // Setup WebSocket after WiFi is connected
  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  
  // Setup web server after WiFi is connected
  setupWebServer();
  
  randomSeed(micros());
  Serial.println("System initialized");
}

void loop() {
  // Handle all services non-blocking
  server.handleClient();
  webSocket.loop();
  client.loop();
  
  checkWifiConnection();
  reconnectMQTT();
  
  unsigned long now = millis();
  
  // Non-blocking sensor reading
  if (isReading && (now - lastSensorRead >= sensorInterval)) {
    long distance = readDistanceNonBlocking();
    
    if (distance >= 0) { // Valid reading
      lastSensorRead = now;
      
      // Store data with millisecond precision
      float timestamp = (float)(now - startTime) / 1000.0;
      String dataEntry = String(timestamp, 3) + "," + String(distance) + ",cm," + currentExperiment;
      sensorData.push_back(dataEntry);
      
      // Send to WebSocket clients
      JsonDocument doc;
      doc["timestamp"] = timestamp;
      doc["distance"] = distance;
      doc["experiment"] = currentExperiment;
      String jsonString;
      serializeJson(doc, jsonString);
      webSocket.broadcastTXT(jsonString);
      
      // MQTT publish (non-blocking)
      if (client.connected()) {
        snprintf(msg, MSG_BUFFER_SIZE, "{\"distance\":%ld,\"timestamp\":%.3f,\"experiment\":\"%s\"}", 
                 distance, timestamp, currentExperiment.c_str());
        client.publish(mqtt_topic, msg);
      }
      
      Serial.printf("Distance: %ld cm, Time: %.3f s\n", distance, timestamp);
    }
  }
  
  yield(); // Allow ESP8266 background tasks
}
