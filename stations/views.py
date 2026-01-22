import io

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import ChargingSession, ChargingStation
from .services import ChargingError, ChargingService


def station_detail(request, station_uuid):
    """
    Station detail page - QR code landing page.
    Shows station info and allows starting/stopping charging.
    """
    station = get_object_or_404(ChargingStation, uuid=station_uuid)

    # Check if user has an active session at this station
    active_session = None
    if request.user.is_authenticated:
        active_session = ChargingSession.objects.filter(
            user=request.user,
            station=station,
            status=ChargingSession.SessionStatus.ACTIVE,
        ).first()

    context = {
        "station": station,
        "active_session": active_session,
    }
    return render(request, "stations/station_detail.html", context)


@login_required
def start_charging(request, station_uuid):
    """Start a charging session at the specified station."""
    if request.method != "POST":
        return redirect("stations:detail", station_uuid=station_uuid)

    station = get_object_or_404(ChargingStation, uuid=station_uuid)

    try:
        session = ChargingService.start_session(request.user, station)
        messages.success(request, f"Charging session started at {station.name}!")

        # TODO: Send MQTT command to ESP32 to enable relay

        return redirect("stations:session", session_id=session.id)
    except ChargingError as e:
        messages.error(request, str(e))
        return redirect("stations:detail", station_uuid=station_uuid)


@login_required
def stop_charging(request, session_id):
    """Stop an active charging session."""
    if request.method != "POST":
        return redirect("accounts:dashboard")

    session = get_object_or_404(ChargingSession, id=session_id, user=request.user)

    if session.status != ChargingSession.SessionStatus.ACTIVE:
        messages.error(request, "This session is not active.")
        return redirect("accounts:dashboard")

    try:
        ChargingService.stop_session(session)
        messages.success(
            request,
            f"Charging session ended. You consumed {session.energy_consumed_kwh:.3f} kWh.",
        )

        # TODO: Send MQTT command to ESP32 to disable relay

        return redirect("accounts:dashboard")
    except ChargingError as e:
        messages.error(request, str(e))
        return redirect("stations:session", session_id=session.id)


@login_required
def session_detail(request, session_id):
    """View an active or completed charging session."""
    session = get_object_or_404(ChargingSession, id=session_id, user=request.user)

    context = {
        "session": session,
        "station": session.station,
    }
    return render(request, "stations/session_detail.html", context)


@login_required
def session_data(request, session_id):
    """API endpoint for getting live session data (AJAX polling)."""
    session = get_object_or_404(ChargingSession, id=session_id, user=request.user)
    station = session.station

    # Calculate current consumption
    current_consumption = 0
    if session.status == ChargingSession.SessionStatus.ACTIVE:
        current_consumption = float(station.current_energy) - float(session.start_energy_kwh)

    data = {
        "session_status": session.status,
        "duration_minutes": session.duration_minutes,
        "start_energy": float(session.start_energy_kwh),
        "current_energy": float(station.current_energy),
        "energy_consumed": max(0, current_consumption),
        "station": {
            "status": station.status,
            "voltage": float(station.current_voltage),
            "current": float(station.current_amperage),
            "power": float(station.current_power),
            "frequency": float(station.current_frequency),
            "power_factor": float(station.current_power_factor),
        },
        "user_balance": float(request.user.profile.balance_kwh),
        "remaining_balance": float(request.user.profile.balance_kwh) - max(0, current_consumption),
    }

    return JsonResponse(data)


@login_required
def session_history(request):
    """View user's charging session history."""
    sessions = ChargingSession.objects.filter(user=request.user).order_by("-started_at")

    context = {
        "sessions": sessions,
    }
    return render(request, "stations/session_history.html", context)


def station_qr_code(request, station_uuid):
    """Generate QR code image for a station."""
    station = get_object_or_404(ChargingStation, uuid=station_uuid)

    # Build the full URL
    # In production, this should use the actual domain
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    url = f"{scheme}://{host}/station/{station.uuid}/"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Return as PNG image
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")


def station_list(request):
    """List all active charging stations."""
    stations = ChargingStation.objects.filter(is_active=True).order_by("name")

    context = {
        "stations": stations,
    }
    return render(request, "stations/station_list.html", context)
