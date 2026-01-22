"""
MQTT message handlers for processing station data.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def extract_station_uuid(topic: str) -> str | None:
    """Extract station UUID from topic path."""
    # Topic format: charging/stations/{uuid}/telemetry
    parts = topic.split("/")
    if len(parts) >= 3:
        return parts[2]  # UUID is the third part
    return None


def handle_telemetry(topic: str, payload: dict):
    """
    Handle telemetry data from stations.

    Expected payload:
    {
        "voltage": 230.5,
        "current": 5.2,
        "power": 1150.0,
        "energy": 12.345,
        "frequency": 50.0,
        "pf": 0.95
    }
    """
    from stations.models import ChargingSession, ChargingStation
    from stations.services import ChargingService

    station_uuid = extract_station_uuid(topic)
    if not station_uuid:
        logger.warning(f"Could not extract station UUID from topic: {topic}")
        return

    try:
        station = ChargingStation.objects.get(uuid=station_uuid)
    except ChargingStation.DoesNotExist:
        logger.warning(f"Station not found: {station_uuid}")
        return

    # Update station telemetry
    station.update_telemetry(payload)
    logger.debug(f"Updated telemetry for station {station.name}: {payload}")

    # Check if there's an active session and balance needs checking
    active_session = ChargingSession.objects.filter(
        station=station,
        status=ChargingSession.SessionStatus.ACTIVE,
    ).first()

    if active_session:
        # Check if user has run out of balance
        was_stopped = ChargingService.check_balance_and_stop(active_session)
        if was_stopped:
            logger.info(f"Session {active_session.id} stopped due to insufficient balance")
            # Send stop command to ESP32
            from mqtt_service.client import mqtt_client

            mqtt_client.stop_charging(station_uuid)


def handle_status(topic: str, payload: dict):
    """
    Handle status updates from stations.

    Expected payload:
    {
        "state": "idle" | "charging",
        "relay": true | false
    }
    """
    from stations.models import ChargingStation

    station_uuid = extract_station_uuid(topic)
    if not station_uuid:
        return

    try:
        station = ChargingStation.objects.get(uuid=station_uuid)
    except ChargingStation.DoesNotExist:
        logger.warning(f"Station not found: {station_uuid}")
        return

    state = payload.get("state", "idle")
    relay = payload.get("relay", False)

    # Update station status
    station.is_occupied = state == "charging" and relay
    station.status = ChargingStation.StationStatus.ONLINE
    station.last_seen = timezone.now()
    station.save(update_fields=["is_occupied", "status", "last_seen", "updated_at"])

    logger.debug(f"Updated status for station {station.name}: state={state}, relay={relay}")


def handle_heartbeat(topic: str, payload: dict):
    """
    Handle heartbeat messages from stations.

    Expected payload:
    {
        "uptime": 12345,
        "rssi": -65,
        "free_heap": 50000
    }
    """
    from stations.models import ChargingStation

    station_uuid = extract_station_uuid(topic)
    if not station_uuid:
        return

    try:
        station = ChargingStation.objects.get(uuid=station_uuid)
    except ChargingStation.DoesNotExist:
        # Could be a new station, log but don't error
        logger.info(f"Heartbeat from unknown station: {station_uuid}")
        return

    station.status = ChargingStation.StationStatus.ONLINE
    station.last_seen = timezone.now()
    station.save(update_fields=["status", "last_seen", "updated_at"])

    logger.debug(f"Heartbeat from {station.name}: uptime={payload.get('uptime')}s")


def register_handlers(mqtt_client):
    """Register all message handlers with the MQTT client."""
    topic_prefix = settings.MQTT_TOPIC_PREFIX

    mqtt_client.register_handler(f"{topic_prefix}/+/telemetry", handle_telemetry)
    mqtt_client.register_handler(f"{topic_prefix}/+/status", handle_status)
    mqtt_client.register_handler(f"{topic_prefix}/+/heartbeat", handle_heartbeat)

    logger.info("Registered MQTT message handlers")
