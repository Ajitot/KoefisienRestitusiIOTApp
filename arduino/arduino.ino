#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiClient.h>
#include <HTTPClient.h>

#define trigPin 14
#define echoPin 27

// Replace with your network credentials
const char* ssid     = "Aji";
const char* password = "12345678";

// supabase credentials
String API_URL = "https://epfsthhwfvafhvfwejhe.supabase.co";
String API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVwZnN0aGh3ZnZhZmh2ZndlamhlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NzgwODY3MywiZXhwIjoyMDYzMzg0NjczfQ.aOVdZcohlqEaHrM4XYOhAJUuJltMAB5GnavVLZjUnIA";
String TableName = "Koefisien";
const int httpsPort = 443;

// Sending interval of the packets in seconds
int sendinginterval = 1; // 20 minutes
//int sendinginterval = 120; // 2 minutes

HTTPClient https;
WiFiClientSecure client;

void setup() {
  // builtIn led is used to indicate when a message is being sent
  //pinMode(LED_BUILTIN, OUTPUT);
  //digitalWrite(LED_BUILTIN, HIGH); // the builtin LED is wired backwards HIGH turns it off

  // HTTPS is used without checking credentials 
  client.setInsecure();

  // Connect to the WIFI 
  Serial.begin(115200);
  
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  // Print local IP address
  Serial.println("");
  Serial.println("WiFi connected.");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
}

void loop() {

   // If connected to the internet turn the Builtin led On and attempt to send a message to the database 
  if (WiFi.status() == WL_CONNECTED) {
    //digitalWrite(LED_BUILTIN, LOW); // LOW turns ON

    // Read all sensors
    long duration;
    float distance,tinggi_objek;
    float SOUND_SPEED = 0.034;

    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);
    duration = pulseIn(echoPin, HIGH);

    distance = (duration / 2)*SOUND_SPEED; // Menghitung jarak dalam sentimeter
    Serial.print("Distance: ");Serial.print(distance);Serial.println(" cm");

    // Send the a post request to the server
    https.begin(client,API_URL+"/rest/v1/"+TableName);
    https.addHeader("Content-Type", "application/json");
    https.addHeader("Prefer", "return=representation");
    https.addHeader("apikey", API_KEY);
    https.addHeader("Authorization", "Bearer " + API_KEY);
    int httpCode = https.POST("{\"High\":" + String(distance)+"}" );   //Send the request
    String payload = https.getString(); 
    Serial.print("httpCode : ");Serial.println(httpCode);   //Print HTTP return code
    Serial.print("payload : ");Serial.println(payload);    //Print request response payload
    https.end();

    //digitalWrite(LED_BUILTIN, HIGH); // HIGH turns off
  }else{
    Serial.println("Error in WiFi connection");
  }
  
}