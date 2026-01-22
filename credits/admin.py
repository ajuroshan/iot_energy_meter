from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .models import CreditTransaction


class AddCreditForm(forms.Form):
    """Form for adding credits to a user."""

    amount_kwh = forms.DecimalField(
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        label="Amount (kWh)",
    )
    description = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Optional description"}),
    )


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount_display",
        "transaction_type",
        "balance_after",
        "added_by",
        "created_at",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = ("user__username", "user__email", "description")
    readonly_fields = (
        "user",
        "amount_kwh",
        "transaction_type",
        "session",
        "added_by",
        "balance_after",
        "created_at",
    )
    raw_id_fields = ("user", "session", "added_by")
    date_hierarchy = "created_at"

    @admin.display(description="Amount (kWh)")
    def amount_display(self, obj):
        if obj.amount_kwh >= 0:
            return f"+{obj.amount_kwh:.3f}"
        return f"{obj.amount_kwh:.3f}"

    def has_add_permission(self, request):
        # Use the custom add credit view instead
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("add-credit/", self.admin_site.admin_view(self.add_credit_view), name="credits_add_credit"),
        ]
        return custom_urls + urls

    def add_credit_view(self, request):
        """Custom view for adding credits to users."""
        from django.contrib.auth.models import User

        if request.method == "POST":
            form = AddCreditForm(request.POST)
            user_id = request.POST.get("user_id")

            if form.is_valid() and user_id:
                try:
                    user = User.objects.get(id=user_id)
                    amount = form.cleaned_data["amount_kwh"]
                    description = form.cleaned_data["description"]

                    CreditTransaction.add_credit(
                        user=user,
                        amount_kwh=amount,
                        added_by=request.user,
                        description=description,
                    )

                    messages.success(
                        request,
                        f"Successfully added {amount} kWh to {user.username}'s account. "
                        f"New balance: {user.profile.balance_kwh} kWh",
                    )
                    return redirect("admin:credits_credittransaction_changelist")

                except User.DoesNotExist:
                    messages.error(request, "User not found.")
        else:
            form = AddCreditForm()

        # Get all users with their balances
        users = User.objects.select_related("profile").filter(is_active=True).order_by("username")

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "users": users,
            "title": "Add Credits to User",
            "opts": self.model._meta,
        }
        return render(request, "admin/credits/add_credit.html", context)

    def add_view(self, request, form_url="", extra_context=None):
        # Redirect to custom add credit view
        return redirect("admin:credits_add_credit")
