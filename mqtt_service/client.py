"""
MQTT Client module for communicating with ESP32 charging stations.
"""

import json
import logging
import threading
from typing import Callable

import paho.mqtt.client as mqtt
from django.conf import settings

logger = logging.getLogger(__name__)


class MQTTClient:
    """Singleton MQTT client for the application."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.broker = settings.MQTT_BROKER
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD
        self.topic_prefix = settings.MQTT_TOPIC_PREFIX

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="django-energy-meter",
        )

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Set authentication if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        # Message handlers
        self._handlers: dict[str, list[Callable]] = {}

        self._initialized = True
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback when connected to broker."""
        if reason_code == 0:
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            self._connected = True

            # Subscribe to all station topics
            topics = [
                f"{self.topic_prefix}/+/telemetry",
                f"{self.topic_prefix}/+/status",
                f"{self.topic_prefix}/+/heartbeat",
            ]
            for topic in topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback when disconnected from broker."""
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")
        self._connected = False

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))

            logger.debug(f"Received message on {topic}: {payload}")

            # Find matching handlers
            for pattern, handlers in self._handlers.items():
                if self._topic_matches(pattern, topic):
                    for handler in handlers:
                        try:
                            handler(topic, payload)
                        except Exception as e:
                            logger.error(f"Error in message handler: {e}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern (supports + and # wildcards)."""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        if len(pattern_parts) != len(topic_parts):
            if "#" not in pattern_parts:
                return False

        for i, (p, t) in enumerate(zip(pattern_parts, topic_parts)):
            if p == "#":
                return True
            if p != "+" and p != t:
                return False

        return len(pattern_parts) == len(topic_parts)

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.disconnect()

    def start_loop(self):
        """Start the MQTT client loop (blocking)."""
        self.client.loop_forever()

    def start_background_loop(self):
        """Start the MQTT client loop in background thread."""
        self.client.loop_start()

    def stop_loop(self):
        """Stop the MQTT client loop."""
        self.client.loop_stop()

    def register_handler(self, topic_pattern: str, handler: Callable):
        """Register a message handler for a topic pattern."""
        if topic_pattern not in self._handlers:
            self._handlers[topic_pattern] = []
        self._handlers[topic_pattern].append(handler)

    def _ensure_connected(self):
        """Ensure the client is connected, reconnecting if necessary."""
        if not self._connected:
            try:
                self.client.connect(self.broker, self.port, keepalive=60)
                self.client.loop_start()
                # Give it a moment to establish connection
                import time
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to reconnect to MQTT broker: {e}")
                return False
        return True

    def publish(self, topic: str, payload: dict, qos: int = 1):
        """Publish a message to a topic."""
        try:
            if not self._ensure_connected():
                logger.error(f"Cannot publish to {topic}: not connected")
                return False
            message = json.dumps(payload)
            result = self.client.publish(topic, message, qos=qos)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    def send_command(self, station_uuid: str, action: str, **kwargs):
        """Send a command to a station."""
        topic = f"{self.topic_prefix}/{station_uuid}/commands"
        payload = {"action": action, **kwargs}
        return self.publish(topic, payload)

    def start_charging(self, station_uuid: str):
        """Send start charging command to station."""
        return self.send_command(station_uuid, "start")

    def stop_charging(self, station_uuid: str):
        """Send stop charging command to station."""
        return self.send_command(station_uuid, "stop")

    def reset_energy(self, station_uuid: str):
        """Send reset energy counter command to station."""
        return self.send_command(station_uuid, "reset")


# Global client instance
mqtt_client = MQTTClient()
