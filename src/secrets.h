// Update these with values suitable for your network.
const char* ssid = "Al muajir";
const char* password = "1618199923";

// **MQTT Broker Cloud**
const char* mqtt_server = "broker.hivemq.com"; //"192.168.1.9";
// **MQTT Broker Local**
const int mqtt_port = 1883;

#ifdef ESP32
  const char* mqtt_topic = "esp32/hcsr04";
#elif defined(ESP8266)
  const char* mqtt_topic = "esp8266/hcsr04";
#endif