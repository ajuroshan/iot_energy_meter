import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class ChargingStation(models.Model):
    """Represents a physical charging station with ESP32 + PZEM."""

    class StationStatus(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        MAINTENANCE = "maintenance", "Maintenance"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=StationStatus.choices,
        default=StationStatus.OFFLINE,
    )
    is_active = models.BooleanField(default=True, help_text="Whether the station is available for use")
    is_occupied = models.BooleanField(default=False, help_text="Whether a charging session is in progress")

    # Heartbeat tracking
    last_seen = models.DateTimeField(null=True, blank=True)

    # Latest readings from PZEM (updated via MQTT)
    current_voltage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    current_amperage = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    current_power = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    current_energy = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    current_frequency = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_power_factor = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Charging Station"
        verbose_name_plural = "Charging Stations"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.uuid})"

    def get_qr_code_url(self):
        """Get the URL that the QR code should point to."""
        return f"/station/{self.uuid}/"

    @property
    def is_online(self):
        """Check if station is online based on last_seen timestamp."""
        if not self.last_seen:
            return False
        # Consider station offline if no heartbeat in last 60 seconds
        timeout = timezone.now() - timezone.timedelta(seconds=60)
        return self.last_seen >= timeout

    @property
    def online_status(self):
        """Get the display status based on real-time online check."""
        if self.is_online:
            return self.StationStatus.ONLINE
        return self.StationStatus.OFFLINE

    @property
    def online_status_display(self):
        """Get human-readable online status."""
        return "Online" if self.is_online else "Offline"

    def update_telemetry(self, data: dict):
        """Update station telemetry data from MQTT message."""
        self.current_voltage = Decimal(str(data.get("voltage", 0)))
        self.current_amperage = Decimal(str(data.get("current", 0)))
        self.current_power = Decimal(str(data.get("power", 0)))
        self.current_energy = Decimal(str(data.get("energy", 0)))
        self.current_frequency = Decimal(str(data.get("frequency", 0)))
        self.current_power_factor = Decimal(str(data.get("pf", 0)))
        self.last_seen = timezone.now()
        self.status = self.StationStatus.ONLINE
        self.save()

    def mark_offline(self):
        """Mark station as offline."""
        self.status = self.StationStatus.OFFLINE
        self.save(update_fields=["status", "updated_at"])


class ChargingSession(models.Model):
    """Represents a single charging session."""

    class SessionStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        STOPPED_NO_CREDIT = "stopped_no_credit", "Stopped - No Credit"
        CANCELLED = "cancelled", "Cancelled"
        ERROR = "error", "Error"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="charging_sessions")
    station = models.ForeignKey(ChargingStation, on_delete=models.CASCADE, related_name="sessions")

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Energy tracking (in kWh)
    start_energy_kwh = models.DecimalField(max_digits=10, decimal_places=3)
    end_energy_kwh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    energy_consumed_kwh = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
    )

    # Notes
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Charging Session"
        verbose_name_plural = "Charging Sessions"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} @ {self.station.name} - {self.started_at}"

    @property
    def duration(self):
        """Calculate session duration."""
        end = self.ended_at or timezone.now()
        return end - self.started_at

    @property
    def duration_minutes(self):
        """Get duration in minutes."""
        return int(self.duration.total_seconds() / 60)

    def calculate_energy_consumed(self, current_energy_kwh: Decimal) -> Decimal:
        """Calculate energy consumed based on current reading."""
        return current_energy_kwh - self.start_energy_kwh

    def end_session(self, end_energy_kwh: Decimal, status: str = None):
        """End the charging session."""
        self.ended_at = timezone.now()
        self.end_energy_kwh = end_energy_kwh
        self.energy_consumed_kwh = self.calculate_energy_consumed(end_energy_kwh)
        self.status = status or self.SessionStatus.COMPLETED

        # Update station
        self.station.is_occupied = False
        self.station.save(update_fields=["is_occupied", "updated_at"])

        self.save()

        return self.energy_consumed_kwh
