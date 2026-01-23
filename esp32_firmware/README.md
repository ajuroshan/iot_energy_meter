# ESP32 Energy Meter Firmware

Production-ready firmware for ESP32 + PZEM-004T energy meter.

---

## Production Server

| Service | URL / Address |
|---------|---------------|
| **Web Dashboard** | http://15.207.150.87 |
| **Admin Panel** | http://15.207.150.87/admin |
| **MQTT Broker** | `15.207.150.87:1883` |

### Credentials

| Service | Username | Password |
|---------|----------|----------|
| Admin Panel | `admin` | `admin123` |

### Station UUIDs (Pre-configured in firmware)

| Device | Station | UUID | Station URL |
|--------|---------|------|-------------|
| `DEVICE_1` | Station 1 | `a079734a-0e2d-4589-9da8-82ce079c6519` | http://15.207.150.87/station/a079734a-0e2d-4589-9da8-82ce079c6519/ |
| `DEVICE_2` | Station 2 | `bce9c8e1-bce0-406c-a182-6285c7f1a5a1` | http://15.207.150.87/station/bce9c8e1-bce0-406c-a182-6285c7f1a5a1/ |

---

## Quick Start - Flash in 3 Steps

### Step 1: Install Arduino IDE & Libraries

1. **Install Arduino IDE** from https://www.arduino.cc/en/software

2. **Add ESP32 Board Support**
   - Go to `File` → `Preferences`
   - Add to "Additional Board Manager URLs":
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to `Tools` → `Board` → `Boards Manager`
   - Search "esp32" and install **ESP32 by Espressif Systems**

3. **Install Libraries** (`Sketch` → `Include Library` → `Manage Libraries`)
   
   | Library | Author |
   |---------|--------|
   | PZEM004Tv30 | Jakub Mandula |
   | PubSubClient | Nick O'Leary |
   | ArduinoJson | Benoit Blanchon |

### Step 2: Configure the Firmware

Open `esp32_firmware.ino` and edit **only these 2 things** at the top of the file:

```cpp
// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                    USER CONFIGURATION - EDIT THIS SECTION                 ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// ┌───────────────────────────────────────────────────────────────────────────┐
// │ STEP 1: Enter your WiFi credentials                                       │
// └──────────────────────────────────────────────'─────────────────────────────┘
#define WIFI_SSID       "MyHomeWiFi"          // <-- Your WiFi network name
#define WIFI_PASSWORD   "MyWiFiPassword123"   // <-- Your WiFi password

// ┌───────────────────────────────────────────────────────────────────────────┐
// │ STEP 2: Select your device (uncomment ONE line only)                      │
// └───────────────────────────────────────────────────────────────────────────┘
#define DEVICE_1        // <-- Uncomment for Station 1
// #define DEVICE_2     // <-- Uncomment for Station 2 (comment out DEVICE_1)
```

**Important:** 
- WiFi must be 2.4GHz (ESP32 doesn't support 5GHz)
- SSID and password are case-sensitive

### Step 3: Upload to ESP32

1. Connect ESP32 via USB cable
2. In Arduino IDE:
   - `Tools` → `Board` → `ESP32 Dev Module`
   - `Tools` → `Port` → Select your COM port (e.g., `COM3` or `/dev/ttyUSB0`)
3. Click **Upload** button (→)
4. Wait for "Done uploading"

---

## Verify It's Working

### 1. Check Serial Monitor

1. `Tools` → `Serial Monitor`
2. Set baud rate to **115200**
3. Press ESP32 reset button
4. You should see:

```
=========================================
   IoT Energy Meter - ESP32 Firmware
=========================================
Station: Station 1
UUID: a079734a-0e2d-4589-9da8-82ce079c6519

Connecting to WiFi: MyHomeWiFi
......
WiFi connected!
IP Address: 192.168.1.105
Signal Strength (RSSI): -45 dBm

Connecting to MQTT broker: 15.207.150.87:1883
MQTT connected!
Subscribed to: charging/stations/a079734a-0e2d-4589-9da8-82ce079c6519/commands

------ Telemetry ------
Voltage:   230.5 V
Current:   0.00 A
Power:     0.0 W
Energy:    0.000 kWh
Frequency: 50.0 Hz
PF:        1.00
Published: OK
-----------------------
```

### 2. Check Production Dashboard

1. Open http://15.207.150.87/station/
2. Your station should show **Online** with a green badge
3. Click on the station to see live readings (voltage, current, power)

### 3. Test Complete Charging Flow

1. **Login to Admin**: http://15.207.150.87/admin
   - Username: `admin`
   - Password: `admin123`

2. **Add Credits to User**:
   - Go to Credits → Add Credit
   - Select user, enter amount (e.g., 100 kWh)
   - Save

3. **Start Charging**:
   - Go to http://15.207.150.87/station/a079734a-0e2d-4589-9da8-82ce079c6519/
   - Click **Start Charging**
   - Watch Serial Monitor for:
     ```
     ------ MQTT Message Received ------
     Payload: {"action":"start"}
     Action: start
     Processing START command...
     Relay ENABLED (ON)
     Charging STARTED
     ```
   - The relay should click ON

4. **Stop Charging**:
   - Click **Stop Charging** on the web page
   - Relay clicks OFF
   - Credits are deducted from user balance

---

## Hardware Setup

### Components Required

| Component | Model | Quantity | Purpose |
|-----------|-------|----------|---------|
| ESP32 | DevKit V1 | 1 | Main controller |
| PZEM-004T | v3.0 | 1 | Energy measurement |
| Relay Module | 5V 1-Channel | 1 | Switch AC power |
| Power Supply | 5V 2A | 1 | Power ESP32 |

### Wiring Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        ESP32 CONNECTIONS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ESP32 Pin        Wire Color      Connect To                   │
│   ─────────        ──────────      ──────────                   │
│   GPIO16 (RX2)  ←  Green        ←  PZEM TX                      │
│   GPIO17 (TX2)  →  Blue         →  PZEM RX                      │
│   GPIO4         →  Any          →  Relay IN                     │
│   5V / VIN      →  Red          →  Relay VCC + PZEM 5V          │
│   GND           →  Black        →  Relay GND + PZEM GND         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 AC WIRING (230V) - HIGH VOLTAGE!                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ⚡ MAINS LIVE (L)  ────────►  PZEM L IN                       │
│   ⚡ MAINS NEUTRAL (N) ──────►  PZEM N IN ────► LOAD NEUTRAL    │
│                                                                 │
│   PZEM L OUT ────────────────►  Relay COM                       │
│   Relay NO (Normally Open) ──►  LOAD LIVE                       │
│                                                                 │
│   When relay activates: COM connects to NO → Power flows        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Pin Reference Table

| ESP32 GPIO | Function | Wire To |
|------------|----------|---------|
| GPIO16 | UART2 RX | PZEM TX (green wire) |
| GPIO17 | UART2 TX | PZEM RX (blue wire) |
| GPIO4 | Relay Control | Relay IN pin |
| GPIO2 | Status LED | Built-in (no wiring needed) |
| 5V/VIN | Power Out | Relay VCC, PZEM 5V |
| GND | Ground | Relay GND, PZEM GND |

---

## LED Status Indicators

The built-in LED (GPIO2) shows the device status:

| LED Pattern | Meaning | Action |
|-------------|---------|--------|
| Fast blink (100ms) | WiFi disconnected | Check WiFi credentials |
| Medium blink (500ms) | MQTT disconnected | Check internet / server |
| Slow blink (2s) | Connected & idle | Ready for charging |
| Solid ON | Charging active | Session in progress |

---

## Safety Warning

**⚠️ DANGER: This project involves HIGH VOLTAGE AC power (230V)**

- Always disconnect mains power before working on the circuit
- Use proper insulation and an enclosed project box
- Keep AC wiring away from low-voltage DC components
- Follow your local electrical codes and regulations
- If you're unsure, consult a licensed electrician
- Never touch exposed wires when power is connected

---

## Troubleshooting

### WiFi Won't Connect

| Issue | Solution |
|-------|----------|
| Wrong credentials | Check SSID and password (case-sensitive) |
| 5GHz network | ESP32 only supports 2.4GHz WiFi |
| Weak signal | Move closer to router, check RSSI in Serial Monitor |
| Hidden network | ESP32 may have issues with hidden SSIDs |

### MQTT Won't Connect

| Issue | Solution |
|-------|----------|
| No internet | Ensure ESP32 can reach the internet |
| Server down | Check if http://15.207.150.87 is accessible |
| Firewall | Ensure port 1883 is not blocked |
| Test connectivity | `ping 15.207.150.87` from your network |

### PZEM Shows NaN / No Reading

| Issue | Solution |
|-------|----------|
| Wrong wiring | TX→RX and RX→TX (crossed) |
| No AC power | PZEM needs AC connected to L IN / N IN |
| Bad connection | Check all wire connections |
| Wrong pins | Verify GPIO16 and GPIO17 |

### Relay Not Working

| Issue | Solution |
|-------|----------|
| No click sound | Check GPIO4 connection |
| Wrong voltage | Relay VCC needs 5V (not 3.3V) |
| Relay LED off | Check relay module power |
| Test relay | Write simple sketch to toggle GPIO4 |

---

## MQTT Protocol Reference

### Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `charging/stations/{UUID}/telemetry` | ESP32 → Server | Energy data every 5s |
| `charging/stations/{UUID}/status` | ESP32 → Server | Relay state changes |
| `charging/stations/{UUID}/heartbeat` | ESP32 → Server | Health check every 30s |
| `charging/stations/{UUID}/commands` | Server → ESP32 | Control commands |

### Telemetry Payload (ESP32 publishes)
```json
{
  "voltage": 230.5,
  "current": 5.25,
  "power": 1150.5,
  "energy": 12.345,
  "frequency": 50.0,
  "pf": 0.95
}
```

### Command Payloads (Server sends)
```json
{"action": "start"}   // Turn relay ON, start charging
{"action": "stop"}    // Turn relay OFF, stop charging
{"action": "reset"}   // Reset PZEM energy counter
{"action": "status"}  // Request current status
```

---

## Testing with MQTT Commands

You can manually send commands to test the ESP32:

### Using mosquitto-clients (install first)

```bash
# Monitor all messages from Station 1
mosquitto_sub -h 15.207.150.87 -p 1883 \
  -t "charging/stations/a079734a-0e2d-4589-9da8-82ce079c6519/#" -v

# Send START command
mosquitto_pub -h 15.207.150.87 -p 1883 \
  -t "charging/stations/a079734a-0e2d-4589-9da8-82ce079c6519/commands" \
  -m '{"action":"start"}'

# Send STOP command
mosquitto_pub -h 15.207.150.87 -p 1883 \
  -t "charging/stations/a079734a-0e2d-4589-9da8-82ce079c6519/commands" \
  -m '{"action":"stop"}'
```

### Using Project Test Scripts

```bash
# From project root directory
cd /home/aju/Works/iot_energy_meter

# Monitor all MQTT traffic
./scripts/mqtt_monitor.sh production

# Run ESP32 simulator (for testing without hardware)
docker compose exec web uv run python scripts/esp32_simulator.py -s 1 -b production
```

---

## Flashing Second Device (Station 2)

To flash the second ESP32 for Station 2:

1. Open `esp32_firmware.ino`
2. Comment out `DEVICE_1`, uncomment `DEVICE_2`:
   ```cpp
   // #define DEVICE_1     // Comment this out
   #define DEVICE_2        // Uncomment this
   ```
3. Connect second ESP32 via USB
4. Select the new COM port
5. Upload

Station 2 will automatically use:
- UUID: `bce9c8e1-bce0-406c-a182-6285c7f1a5a1`
- Client ID: `esp32-station-2`
- Dashboard: http://15.207.150.87/station/bce9c8e1-bce0-406c-a182-6285c7f1a5a1/
