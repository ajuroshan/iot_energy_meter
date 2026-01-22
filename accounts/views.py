from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from stations.models import ChargingSession

from .forms import UserRegistrationForm


def register(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome to Energy Meter.")
            return redirect("accounts:dashboard")
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard(request):
    """User dashboard showing balance and recent activity."""
    profile = request.user.profile

    # Get active session if any
    active_session = ChargingSession.objects.filter(user=request.user, status="active").first()

    # Get recent sessions
    recent_sessions = ChargingSession.objects.filter(user=request.user).order_by("-started_at")[:5]

    context = {
        "profile": profile,
        "active_session": active_session,
        "recent_sessions": recent_sessions,
    }
    return render(request, "accounts/dashboard.html", context)


@login_required
def profile(request):
    """User profile view and edit."""
    user_profile = request.user.profile

    if request.method == "POST":
        # Update user info
        request.user.first_name = request.POST.get("first_name", "")
        request.user.last_name = request.POST.get("last_name", "")
        request.user.save()

        # Update profile
        user_profile.phone = request.POST.get("phone", "")
        user_profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("accounts:profile")

    return render(request, "accounts/profile.html", {"profile": user_profile})
