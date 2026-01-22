#!/usr/bin/env python3
"""
ESP32 Simulator for IoT Energy Meter

This script simulates an ESP32 device with PZEM-004T sensor for testing
the MQTT communication with the Django backend without actual hardware.

Features:
- Publishes telemetry data (voltage, current, power, energy) every 5 seconds
- Publishes heartbeat every 30 seconds
- Subscribes to commands topic and responds to start/stop commands
- Simulates energy accumulation during charging sessions
- Tracks and displays session statistics

Usage:
    python esp32_simulator.py --station 1 --broker 15.207.150.87
    python esp32_simulator.py --station 2 --broker localhost
    python esp32_simulator.py --help
"""

import argparse
import json
import random
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed")
    print("Install with: pip install paho-mqtt")
    sys.exit(1)


# Station configurations
STATIONS = {
    1: {
        "uuid": "a079734a-0e2d-4589-9da8-82ce079c6519",
        "name": "Station 1",
        "client_id": "esp32-simulator-station-1",
    },
    2: {
        "uuid": "bce9c8e1-bce0-406c-a182-6285c7f1a5a1",
        "name": "Station 2",
        "client_id": "esp32-simulator-station-2",
    },
}

# Default broker configurations
BROKERS = {
    "production": "15.207.150.87",
    "local": "localhost",
}

# MQTT topic prefix
TOPIC_PREFIX = "charging/stations"

# Timing intervals (seconds)
TELEMETRY_INTERVAL = 5
HEARTBEAT_INTERVAL = 30


@dataclass
class SimulatorState:
    """Tracks the state of the simulated ESP32."""

    is_charging: bool = False
    relay_state: bool = False
    energy_kwh: float = 0.0
    session_start_time: float = None
    session_energy_start: float = 0.0
    uptime_start: float = None
    last_telemetry: float = 0
    last_heartbeat: float = 0

    # Simulated sensor readings (when idle)
    base_voltage: float = 230.0
    base_frequency: float = 50.0


class ESP32Simulator:
    """Simulates an ESP32 charging station."""

    def __init__(self, station_num: int, broker: str, port: int = 1883):
        if station_num not in STATIONS:
            raise ValueError(f"Invalid station number: {station_num}. Must be 1 or 2.")

        self.station = STATIONS[station_num]
        self.broker = broker
        self.port = port
        self.state = SimulatorState()
        self.state.uptime_start = time.time()
        self.running = False

        # Build topic names
        uuid = self.station["uuid"]
        self.topic_telemetry = f"{TOPIC_PREFIX}/{uuid}/telemetry"
        self.topic_status = f"{TOPIC_PREFIX}/{uuid}/status"
        self.topic_heartbeat = f"{TOPIC_PREFIX}/{uuid}/heartbeat"
        self.topic_commands = f"{TOPIC_PREFIX}/{uuid}/commands"

        # Create MQTT client
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.station["client_id"],
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Called when connected to MQTT broker."""
        if reason_code == 0:
            self._log("Connected to MQTT broker")
            # Subscribe to commands
            client.subscribe(self.topic_commands)
            self._log(f"Subscribed to: {self.topic_commands}")
            # Publish initial status
            self._publish_status()
            self._publish_heartbeat()
        else:
            self._log(f"Connection failed: {reason_code}", error=True)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Called when disconnected from MQTT broker."""
        self._log(f"Disconnected from broker: {reason_code}", error=True)

    def _on_message(self, client, userdata, msg):
        """Called when message received."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))

            self._log(f"Command received: {payload}")

            action = payload.get("action")
            if action == "start":
                self._handle_start()
            elif action == "stop":
                self._handle_stop()
            elif action == "reset":
                self._handle_reset()
            elif action == "status":
                self._publish_status()
            else:
                self._log(f"Unknown action: {action}", error=True)

        except json.JSONDecodeError:
            self._log(f"Invalid JSON: {msg.payload}", error=True)
        except Exception as e:
            self._log(f"Error processing message: {e}", error=True)

    def _handle_start(self):
        """Handle start charging command."""
        if self.state.is_charging:
            self._log("Already charging, ignoring start command")
            return

        self._log("Starting charging session...")
        self.state.is_charging = True
        self.state.relay_state = True
        self.state.session_start_time = time.time()
        self.state.session_energy_start = self.state.energy_kwh
        self._publish_status()
        self._log("Charging STARTED - Relay ON")

    def _handle_stop(self):
        """Handle stop charging command."""
        if not self.state.is_charging:
            self._log("Not charging, ignoring stop command")
            return

        self._log("Stopping charging session...")
        session_duration = time.time() - self.state.session_start_time
        session_energy = self.state.energy_kwh - self.state.session_energy_start

        self.state.is_charging = False
        self.state.relay_state = False
        self.state.session_start_time = None
        self._publish_status()

        self._log(f"Charging STOPPED - Relay OFF")
        self._log(f"Session duration: {session_duration:.1f}s, Energy used: {session_energy:.4f} kWh")

    def _handle_reset(self):
        """Handle reset energy counter command."""
        self._log("Resetting energy counter...")
        self.state.energy_kwh = 0.0
        self._publish_telemetry()
        self._log("Energy counter reset to 0")

    def _generate_telemetry(self) -> dict:
        """Generate simulated sensor readings."""
        # Add small random variations to base values
        voltage = self.state.base_voltage + random.uniform(-2, 2)
        frequency = self.state.base_frequency + random.uniform(-0.2, 0.2)

        if self.state.is_charging:
            # Simulate charging: 5-15A current draw
            current = random.uniform(5.0, 15.0)
            power = voltage * current * random.uniform(0.9, 1.0)  # Account for power factor
            pf = random.uniform(0.92, 0.99)

            # Accumulate energy (power in watts, convert to kWh)
            # energy = power * time_hours
            time_hours = TELEMETRY_INTERVAL / 3600
            energy_delta = (power / 1000) * time_hours
            self.state.energy_kwh += energy_delta
        else:
            # Idle state: minimal readings
            current = random.uniform(0.0, 0.05)
            power = voltage * current
            pf = 1.0 if current < 0.01 else random.uniform(0.95, 1.0)

        return {
            "voltage": round(voltage, 1),
            "current": round(current, 3),
            "power": round(power, 1),
            "energy": round(self.state.energy_kwh, 4),
            "frequency": round(frequency, 1),
            "pf": round(pf, 2),
        }

    def _publish_telemetry(self):
        """Publish telemetry data."""
        data = self._generate_telemetry()
        self.client.publish(self.topic_telemetry, json.dumps(data))

        status = "CHARGING" if self.state.is_charging else "IDLE"
        self._log(
            f"Telemetry [{status}]: "
            f"V={data['voltage']}V, I={data['current']}A, "
            f"P={data['power']}W, E={data['energy']}kWh"
        )

    def _publish_status(self):
        """Publish status."""
        data = {
            "state": "charging" if self.state.is_charging else "idle",
            "relay": self.state.relay_state,
        }
        self.client.publish(self.topic_status, json.dumps(data))
        self._log(f"Status: {data}")

    def _publish_heartbeat(self):
        """Publish heartbeat."""
        uptime = int(time.time() - self.state.uptime_start)
        data = {
            "uptime": uptime,
            "rssi": random.randint(-70, -40),  # Simulated WiFi signal
            "free_heap": random.randint(150000, 200000),
            "relay": self.state.relay_state,
        }
        self.client.publish(self.topic_heartbeat, json.dumps(data))
        self._log(f"Heartbeat: uptime={uptime}s, relay={'ON' if self.state.relay_state else 'OFF'}")

    def _log(self, message: str, error: bool = False):
        """Print a timestamped log message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] [{self.station['name']}]"
        if error:
            print(f"{prefix} ERROR: {message}", file=sys.stderr)
        else:
            print(f"{prefix} {message}")

    def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            self._log(f"Connecting to {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            return True
        except Exception as e:
            self._log(f"Connection failed: {e}", error=True)
            return False

    def run(self):
        """Main loop."""
        if not self.connect():
            return

        self.running = True
        self.client.loop_start()

        self._log("Simulator running. Press Ctrl+C to stop.")
        print("-" * 60)

        try:
            while self.running:
                now = time.time()

                # Publish telemetry
                if now - self.state.last_telemetry >= TELEMETRY_INTERVAL:
                    self._publish_telemetry()
                    self.state.last_telemetry = now

                # Publish heartbeat
                if now - self.state.last_heartbeat >= HEARTBEAT_INTERVAL:
                    self._publish_heartbeat()
                    self.state.last_heartbeat = now

                time.sleep(0.1)

        except KeyboardInterrupt:
            self._log("Shutting down...")
        finally:
            self.running = False
            self.client.loop_stop()
            self.client.disconnect()
            self._log("Disconnected")

    def stop(self):
        """Stop the simulator."""
        self.running = False


def main():
    parser = argparse.ArgumentParser(
        description="ESP32 Simulator for IoT Energy Meter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --station 1 --broker 15.207.150.87   # Station 1 on production
  %(prog)s --station 2 --broker localhost       # Station 2 on local
  %(prog)s -s 1 -b production                   # Use 'production' alias
  %(prog)s -s 1 -b local                        # Use 'local' alias

Station UUIDs:
  Station 1: a079734a-0e2d-4589-9da8-82ce079c6519
  Station 2: bce9c8e1-bce0-406c-a182-6285c7f1a5a1
        """,
    )
    parser.add_argument(
        "-s",
        "--station",
        type=int,
        choices=[1, 2],
        default=1,
        help="Station number (1 or 2, default: 1)",
    )
    parser.add_argument(
        "-b",
        "--broker",
        type=str,
        default="production",
        help="MQTT broker address or alias (production/local, default: production)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)",
    )

    args = parser.parse_args()

    # Resolve broker alias
    broker = BROKERS.get(args.broker, args.broker)

    print("=" * 60)
    print("  IoT Energy Meter - ESP32 Simulator")
    print("=" * 60)
    print(f"  Station:  {STATIONS[args.station]['name']}")
    print(f"  UUID:     {STATIONS[args.station]['uuid']}")
    print(f"  Broker:   {broker}:{args.port}")
    print("=" * 60)
    print()

    simulator = ESP32Simulator(args.station, broker, args.port)

    # Handle SIGTERM for graceful shutdown
    def signal_handler(signum, frame):
        simulator.stop()

    signal.signal(signal.SIGTERM, signal_handler)

    simulator.run()


if __name__ == "__main__":
    main()
