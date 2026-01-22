/*
 * IoT Energy Meter - ESP32 Firmware
 * Production Ready - AWS Server: 15.207.150.87
 * 
 * This firmware reads energy data from PZEM-004T sensor and sends it to
 * Django backend via MQTT. It also receives commands to control a relay
 * for starting/stopping charging sessions.
 * 
 * Hardware:
 *   - ESP32 DevKit V1
 *   - PZEM-004T v3.0 Energy Meter
 *   - 5V Relay Module
 * 
 * Wiring:
 *   ESP32 GPIO16 (RX2) <-- PZEM TX (Green)
 *   ESP32 GPIO17 (TX2) --> PZEM RX (Blue)
 *   ESP32 GPIO4        --> Relay IN
 *   ESP32 GPIO2        --> Built-in LED (status)
 *   ESP32 GND          --> PZEM GND, Relay GND
 *   ESP32 5V/VIN       --> Relay VCC
 * 
 * Required Libraries (install via Arduino Library Manager):
 *   - PZEM004Tv30 by Jakub Mandula
 *   - PubSubClient by Nick O'Leary
 *   - ArduinoJson by Benoit Blanchon
 * 
 * Instructions:
 *   1. Install the required libraries above
 *   2. Select your ESP32 board in Tools > Board
 *   3. Update WIFI_SSID and WIFI_PASSWORD below
 *   4. Select DEVICE_1 or DEVICE_2 (uncomment one)
 *   5. Upload to your ESP32
 * 
 * Author: IoT Energy Meter Project
 * Date: 2026
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <PZEM004Tv30.h>
#include <ArduinoJson.h>

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                    USER CONFIGURATION - EDIT THIS SECTION                 ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// ┌───────────────────────────────────────────────────────────────────────────┐
// │ STEP 1: Enter your WiFi credentials                                       │
// └───────────────────────────────────────────────────────────────────────────┘
#define WIFI_SSID       "IPhone"      // <-- Enter your WiFi name
#define WIFI_PASSWORD   "987667899"  // <-- Enter your WiFi password

// ┌───────────────────────────────────────────────────────────────────────────┐
// │ STEP 2: Select your device (uncomment ONE line only)                      │
// └───────────────────────────────────────────────────────────────────────────┘
#define DEVICE_1        // Station 1 - UUID: a079734a-0e2d-4589-9da8-82ce079c6519
// #define DEVICE_2     // Station 2 - UUID: bce9c8e1-bce0-406c-a182-6285c7f1a5a1

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║              PRODUCTION CONFIGURATION - DO NOT MODIFY BELOW               ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// Device-specific configuration (based on selection above)
#ifdef DEVICE_1
  #define STATION_UUID    "a079734a-0e2d-4589-9da8-82ce079c6519"
  #define STATION_NAME    "Station 1"
  #define MQTT_CLIENT_ID  "esp32-station-1"
#endif

#ifdef DEVICE_2
  #define STATION_UUID    "bce9c8e1-bce0-406c-a182-6285c7f1a5a1"
  #define STATION_NAME    "Station 2"
  #define MQTT_CLIENT_ID  "esp32-station-2"
#endif

// MQTT Broker - AWS Production Server
#define MQTT_BROKER     "15.207.150.87"
#define MQTT_PORT       1883
#define MQTT_USERNAME   ""                     // Leave empty (no auth)
#define MQTT_PASSWORD   ""                     // Leave empty (no auth)

// MQTT Topics (auto-generated from UUID)
#define MQTT_TOPIC_PREFIX "charging/stations"

// Hardware Pin Configuration
#define PZEM_RX_PIN     16    // ESP32 RX2 <- PZEM TX
#define PZEM_TX_PIN     17    // ESP32 TX2 -> PZEM RX
#define RELAY_PIN       4     // Relay control pin
#define LED_PIN         2     // Built-in LED (status indicator)

// Timing Configuration (milliseconds)
#define TELEMETRY_INTERVAL    5000    // Send telemetry every 5 seconds
#define HEARTBEAT_INTERVAL    30000   // Send heartbeat every 30 seconds
#define WIFI_RETRY_DELAY      5000    // Wait 5 seconds between WiFi retries
#define MQTT_RETRY_DELAY      5000    // Wait 5 seconds between MQTT retries
#define WATCHDOG_TIMEOUT      300000  // 5 minutes - disable relay if no MQTT

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

// WiFi and MQTT clients
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// PZEM sensor on Serial2
PZEM004Tv30 pzem(Serial2, PZEM_RX_PIN, PZEM_TX_PIN);

// ============================================================================
// GLOBAL STATE VARIABLES
// ============================================================================

bool relayState = false;              // Current relay state
bool isCharging = false;              // Charging session active
unsigned long lastTelemetryTime = 0;  // Last telemetry publish time
unsigned long lastHeartbeatTime = 0;  // Last heartbeat publish time
unsigned long lastMqttActivity = 0;   // Last MQTT message received time

// MQTT Topics (constructed in setup)
String topicTelemetry;
String topicStatus;
String topicHeartbeat;
String topicCommands;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize serial for debugging
  Serial.begin(115200);
  delay(1000);
  
  Serial.println();
  Serial.println("=========================================");
  Serial.println("   IoT Energy Meter - ESP32 Firmware");
  Serial.println("=========================================");
  Serial.print("Station: ");
  Serial.println(STATION_NAME);
  Serial.print("UUID: ");
  Serial.println(STATION_UUID);
  Serial.println();

  // Initialize GPIO pins
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  
  // Ensure relay is OFF on boot (safe default)
  digitalWrite(RELAY_PIN, LOW);
  relayState = false;
  isCharging = false;
  
  // Blink LED to indicate startup
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(100);
  }

  // Construct MQTT topics
  topicTelemetry = String(MQTT_TOPIC_PREFIX) + "/" + STATION_UUID + "/telemetry";
  topicStatus = String(MQTT_TOPIC_PREFIX) + "/" + STATION_UUID + "/status";
  topicHeartbeat = String(MQTT_TOPIC_PREFIX) + "/" + STATION_UUID + "/heartbeat";
  topicCommands = String(MQTT_TOPIC_PREFIX) + "/" + STATION_UUID + "/commands";

  Serial.println("MQTT Topics:");
  Serial.println("  Telemetry: " + topicTelemetry);
  Serial.println("  Status: " + topicStatus);
  Serial.println("  Commands: " + topicCommands);
  Serial.println();

  // Connect to WiFi
  setupWiFi();

  // Configure MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);

  // Connect to MQTT
  connectMQTT();

  // Initialize timing
  lastTelemetryTime = millis();
  lastHeartbeatTime = millis();
  lastMqttActivity = millis();

  Serial.println("Setup complete!");
  Serial.println();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Ensure WiFi is connected
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    setupWiFi();
  }

  // Ensure MQTT is connected
  if (!mqttClient.connected()) {
    connectMQTT();
  }

  // Process MQTT messages
  mqttClient.loop();

  // Current time
  unsigned long currentTime = millis();

  // Publish telemetry every TELEMETRY_INTERVAL
  if (currentTime - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    publishTelemetry();
    lastTelemetryTime = currentTime;
  }

  // Publish heartbeat every HEARTBEAT_INTERVAL
  if (currentTime - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
    publishHeartbeat();
    lastHeartbeatTime = currentTime;
  }

  // Watchdog: If no MQTT activity for WATCHDOG_TIMEOUT, disable relay
  if (isCharging && (currentTime - lastMqttActivity >= WATCHDOG_TIMEOUT)) {
    Serial.println("WATCHDOG: No MQTT activity, stopping charging for safety");
    disableRelay();
    publishStatus();
  }

  // Update LED status
  updateStatusLED();

  // Small delay to prevent overwhelming the CPU
  delay(10);
}

// ============================================================================
// WIFI FUNCTIONS
// ============================================================================

void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println();
    Serial.println("WiFi connection failed! Will retry...");
  }
}

// ============================================================================
// MQTT FUNCTIONS
// ============================================================================

void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT broker: ");
    Serial.print(MQTT_BROKER);
    Serial.print(":");
    Serial.println(MQTT_PORT);

    bool connected = false;
    
    if (strlen(MQTT_USERNAME) > 0) {
      connected = mqttClient.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD);
    } else {
      connected = mqttClient.connect(MQTT_CLIENT_ID);
    }

    if (connected) {
      Serial.println("MQTT connected!");
      
      // Subscribe to commands topic
      mqttClient.subscribe(topicCommands.c_str());
      Serial.println("Subscribed to: " + topicCommands);

      // Publish initial status
      publishStatus();
      publishHeartbeat();
      
      // Update activity timestamp
      lastMqttActivity = millis();
      
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(". Retrying in 5 seconds...");
      delay(MQTT_RETRY_DELAY);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Update activity timestamp
  lastMqttActivity = millis();

  // Convert payload to string
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.println();
  Serial.println("------ MQTT Message Received ------");
  Serial.print("Topic: ");
  Serial.println(topic);
  Serial.print("Payload: ");
  Serial.println(message);

  // Parse JSON
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, message);

  if (error) {
    Serial.print("JSON parse error: ");
    Serial.println(error.c_str());
    return;
  }

  // Handle commands
  const char* action = doc["action"];
  
  if (action == nullptr) {
    Serial.println("No 'action' field in message");
    return;
  }

  Serial.print("Action: ");
  Serial.println(action);

  if (strcmp(action, "start") == 0) {
    handleStartCommand();
  } else if (strcmp(action, "stop") == 0) {
    handleStopCommand();
  } else if (strcmp(action, "reset") == 0) {
    handleResetCommand();
  } else if (strcmp(action, "status") == 0) {
    publishStatus();
  } else {
    Serial.println("Unknown action: " + String(action));
  }

  Serial.println("-----------------------------------");
}

// ============================================================================
// COMMAND HANDLERS
// ============================================================================

void handleStartCommand() {
  Serial.println("Processing START command...");
  
  // Check if voltage is present (safety check)
  float voltage = pzem.voltage();
  if (isnan(voltage) || voltage < 100) {
    Serial.println("ERROR: No voltage detected, cannot start charging");
    return;
  }
  
  enableRelay();
  publishStatus();
  Serial.println("Charging STARTED");
}

void handleStopCommand() {
  Serial.println("Processing STOP command...");
  disableRelay();
  publishStatus();
  Serial.println("Charging STOPPED");
}

void handleResetCommand() {
  Serial.println("Processing RESET command...");
  
  // Reset PZEM energy counter
  if (pzem.resetEnergy()) {
    Serial.println("PZEM energy counter reset successfully");
  } else {
    Serial.println("Failed to reset PZEM energy counter");
  }
  
  publishTelemetry();
}

// ============================================================================
// RELAY CONTROL
// ============================================================================

void enableRelay() {
  digitalWrite(RELAY_PIN, HIGH);
  relayState = true;
  isCharging = true;
  Serial.println("Relay ENABLED (ON)");
}

void disableRelay() {
  digitalWrite(RELAY_PIN, LOW);
  relayState = false;
  isCharging = false;
  Serial.println("Relay DISABLED (OFF)");
}

// ============================================================================
// PUBLISH FUNCTIONS
// ============================================================================

void publishTelemetry() {
  // Read all values from PZEM
  float voltage = pzem.voltage();
  float current = pzem.current();
  float power = pzem.power();
  float energy = pzem.energy();
  float frequency = pzem.frequency();
  float pf = pzem.pf();

  // Check for read errors
  if (isnan(voltage)) {
    Serial.println("Error reading PZEM data");
    // Publish error status
    StaticJsonDocument<128> doc;
    doc["error"] = "PZEM read failed";
    doc["timestamp"] = millis();
    
    String output;
    serializeJson(doc, output);
    mqttClient.publish(topicTelemetry.c_str(), output.c_str());
    return;
  }

  // Create JSON payload
  StaticJsonDocument<256> doc;
  doc["voltage"] = round(voltage * 10) / 10.0;      // 1 decimal place
  doc["current"] = round(current * 1000) / 1000.0;  // 3 decimal places
  doc["power"] = round(power * 10) / 10.0;          // 1 decimal place
  doc["energy"] = round(energy * 1000) / 1000.0;    // 3 decimal places (kWh)
  doc["frequency"] = round(frequency * 10) / 10.0;  // 1 decimal place
  doc["pf"] = round(pf * 100) / 100.0;              // 2 decimal places

  String output;
  serializeJson(doc, output);

  // Publish
  bool success = mqttClient.publish(topicTelemetry.c_str(), output.c_str());
  
  // Debug output
  Serial.println();
  Serial.println("------ Telemetry ------");
  Serial.print("Voltage:   "); Serial.print(voltage); Serial.println(" V");
  Serial.print("Current:   "); Serial.print(current); Serial.println(" A");
  Serial.print("Power:     "); Serial.print(power); Serial.println(" W");
  Serial.print("Energy:    "); Serial.print(energy); Serial.println(" kWh");
  Serial.print("Frequency: "); Serial.print(frequency); Serial.println(" Hz");
  Serial.print("PF:        "); Serial.println(pf);
  Serial.print("Published: "); Serial.println(success ? "OK" : "FAILED");
  Serial.println("-----------------------");
}

void publishStatus() {
  StaticJsonDocument<128> doc;
  doc["state"] = isCharging ? "charging" : "idle";
  doc["relay"] = relayState;

  String output;
  serializeJson(doc, output);

  mqttClient.publish(topicStatus.c_str(), output.c_str());
  
  Serial.print("Status published: ");
  Serial.println(output);
}

void publishHeartbeat() {
  StaticJsonDocument<128> doc;
  doc["uptime"] = millis() / 1000;  // Seconds since boot
  doc["rssi"] = WiFi.RSSI();        // WiFi signal strength
  doc["free_heap"] = ESP.getFreeHeap();
  doc["relay"] = relayState;

  String output;
  serializeJson(doc, output);

  mqttClient.publish(topicHeartbeat.c_str(), output.c_str());
  
  Serial.print("Heartbeat: uptime=");
  Serial.print(millis() / 1000);
  Serial.print("s, RSSI=");
  Serial.print(WiFi.RSSI());
  Serial.print("dBm, heap=");
  Serial.println(ESP.getFreeHeap());
}

// ============================================================================
// STATUS LED
// ============================================================================

void updateStatusLED() {
  static unsigned long lastBlink = 0;
  static bool ledState = false;
  unsigned long currentTime = millis();

  if (WiFi.status() != WL_CONNECTED) {
    // Fast blink: WiFi disconnected
    if (currentTime - lastBlink >= 100) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
      lastBlink = currentTime;
    }
  } else if (!mqttClient.connected()) {
    // Medium blink: MQTT disconnected
    if (currentTime - lastBlink >= 500) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
      lastBlink = currentTime;
    }
  } else if (isCharging) {
    // Solid ON: Charging
    digitalWrite(LED_PIN, HIGH);
  } else {
    // Slow blink: Idle, connected
    if (currentTime - lastBlink >= 2000) {
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState);
      lastBlink = currentTime;
    }
  }
}
