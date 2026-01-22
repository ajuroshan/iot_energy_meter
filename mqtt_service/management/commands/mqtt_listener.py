"""
Django management command to run the MQTT listener.
"""

import logging
import signal
import sys
import time

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the MQTT listener for receiving station data"

    def __init__(self):
        super().__init__()
        self.running = True

    def handle(self, *args, **options):
        from mqtt_service.client import mqtt_client
        from mqtt_service.handlers import register_handlers

        self.stdout.write("Starting MQTT listener...")

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Register message handlers
        register_handlers(mqtt_client)

        # Connect to broker
        max_retries = 5
        retry_delay = 5

        for attempt in range(max_retries):
            if mqtt_client.connect():
                break

            self.stdout.write(
                self.style.WARNING(
                    f"Connection attempt {attempt + 1}/{max_retries} failed. Retrying in {retry_delay}s..."
                )
            )
            time.sleep(retry_delay)
        else:
            self.stdout.write(self.style.ERROR("Failed to connect to MQTT broker after max retries"))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS("MQTT listener connected and running"))

        # Run the client loop
        try:
            mqtt_client.start_loop()
        except Exception as e:
            logger.error(f"MQTT listener error: {e}")
        finally:
            mqtt_client.disconnect()
            self.stdout.write("MQTT listener stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.stdout.write("\nShutting down MQTT listener...")
        self.running = False

        from mqtt_service.client import mqtt_client

        mqtt_client.disconnect()
        sys.exit(0)
