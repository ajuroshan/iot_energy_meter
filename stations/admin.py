from django.contrib import admin
from django.utils.html import format_html

from .models import ChargingSession, ChargingStation


@admin.register(ChargingStation)
class ChargingStationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "uuid_short",
        "status",
        "is_active",
        "is_occupied",
        "current_power",
        "last_seen",
    )
    list_filter = ("status", "is_active", "is_occupied")
    search_fields = ("name", "uuid", "location")
    readonly_fields = (
        "uuid",
        "last_seen",
        "current_voltage",
        "current_amperage",
        "current_power",
        "current_energy",
        "current_frequency",
        "current_power_factor",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("name", "uuid", "location", "description")}),
        ("Status", {"fields": ("status", "is_active", "is_occupied", "last_seen")}),
        (
            "Current Readings",
            {
                "fields": (
                    "current_voltage",
                    "current_amperage",
                    "current_power",
                    "current_energy",
                    "current_frequency",
                    "current_power_factor",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="UUID")
    def uuid_short(self, obj):
        return str(obj.uuid)[:8]


@admin.register(ChargingSession)
class ChargingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "station",
        "status",
        "started_at",
        "ended_at",
        "energy_consumed_display",
        "duration_display",
    )
    list_filter = ("status", "station", "started_at")
    search_fields = ("user__username", "station__name")
    readonly_fields = (
        "started_at",
        "ended_at",
        "start_energy_kwh",
        "end_energy_kwh",
        "energy_consumed_kwh",
    )
    raw_id_fields = ("user", "station")

    @admin.display(description="Energy (kWh)")
    def energy_consumed_display(self, obj):
        if obj.energy_consumed_kwh:
            return f"{obj.energy_consumed_kwh:.3f}"
        return "-"

    @admin.display(description="Duration")
    def duration_display(self, obj):
        if obj.status == "active":
            return format_html('<span style="color: green;">In Progress</span>')
        minutes = obj.duration_minutes
        if minutes < 60:
            return f"{minutes} min"
        hours = minutes // 60
        remaining_mins = minutes % 60
        return f"{hours}h {remaining_mins}m"
