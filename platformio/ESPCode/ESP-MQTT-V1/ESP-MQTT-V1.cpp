#ifdef ESP32
  #include <WiFi.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
#endif

#include <PubSubClient.h>

// Update these with values suitable for your network.

const char* ssid = "Al muajir";
const char* password = "1618199923";
// **MQTT Broker Cloud**
const char* mqtt_server = "broker.mqtt-dashboard.com";
// **MQTT Broker Local**
const int mqtt_port = 1883;

#ifdef ESP32
  const char* mqtt_topic = "esp32/hcsr04";
#elif defined(ESP8266)
  const char* mqtt_topic = "esp8266/hcsr04";
#endif

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
unsigned long lastMsg = 0;
#define MSG_BUFFER_SIZE	(50)
char msg[MSG_BUFFER_SIZE];
int value = 0;

// HC-SR04 functions
long readDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH);
  long distance = duration * 0.034 / 2; // Convert to cm
  
  return distance;
}

void setup_wifi() {

  delay(10);
  // We start by connecting to a WiFi network
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

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
    long distance = readDistance();
    snprintf(msg, MSG_BUFFER_SIZE, "Distance: %ld cm", distance);
    client.publish(mqtt_topic, msg);
    Serial.println("Distance reading requested and sent");
  }
  // Switch on the LED if an 1 was received as first character
  else if ((char)payload[0] == '1') {
    digitalWrite(LED_BUILTIN, LOW);
  } else {
    digitalWrite(LED_BUILTIN, HIGH);
  }

}

void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Create a random client ID
    String clientId = "ESP8266Client-";
    clientId += String(random(0xffff), HEX);
    // Attempt to connect
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      // Once connected, publish an announcement...
      client.publish(mqtt_topic, "hello world");
      // ... and resubscribe
      client.subscribe(mqtt_topic);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.begin(115200);
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {

  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastMsg > 100) { // Send every 5 seconds
    lastMsg = now;
    
    // Read distance from HC-SR04
    long distance = readDistance();
    
    snprintf(msg, MSG_BUFFER_SIZE, "{\"distance\":%ld,\"unit\":\"cm\"}", distance);
    Serial.print("Publish message: ");
    Serial.println(msg);
    client.publish(mqtt_topic, msg);
  }
}
