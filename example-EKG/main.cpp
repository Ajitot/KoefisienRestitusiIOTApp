#include <WiFi.h>
#include <PubSubClient.h>

// Ganti dengan WiFi dan MQTT Anda
const char* ssid = "Redmi Note 10 5G";
const char* password = "alyaaurora";
const char* mqtt_server = "broker.hivemq.com";

const int MUX = 32;          // Lead-off detection +
const int LO_MINUS = 33;     // lead-off detection
const int EKG_PIN = 34;      // ADC input dari AD8232

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastTime = 0;
unsigned long interval = 2; // 2 ms = 500 Hz

void reconnect() {
  while (!client.connected()) {
    Serial.print("Menyambungkan ke MQTT...");
    if (client.connect("ESP32EKG")) {
      Serial.println("Berhasil!");
    } else {
      Serial.print("Gagal, kode = ");
      Serial.print(client.state());
      delay(1000);
    }
  }
}

void setup_wifi() {
  delay(10);
  Serial.println("Menghubungkan ke WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("Terhubung ke WiFi!");
}

void setup() {
  Serial.begin(115200);
  pinMode(LO_MINUS, INPUT);
  pinMode(MUX, INPUT);
  analogSetAttenuation(ADC_11db); // agar bisa membaca 3.3V

  setup_wifi();
  client.setServer(mqtt_server, 1883);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastTime >= interval) {
    lastTime = now;

    if (digitalRead(LO_MINUS) == 1) {
      Serial.println("{\"status\":\"LEAD OFF\"}");
      return;
    }

    // Baca sinyal dari pin
    int raw = analogRead(EKG_PIN);
    float voltage = raw * (3.3 / 4095.0); // Konversi ke volt
    float time = now / 1000.0;

    String payload = "{\"time\":" + String(time, 3) + ",\"voltage\":" + String(voltage, 3) + "}";
    client.publish("telemed/ekg", payload.c_str());
    Serial.println(payload);
  }
}