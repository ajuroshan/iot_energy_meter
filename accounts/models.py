from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    """Extended user profile with credit balance."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    balance_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="User's credit balance in kWh",
    )
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} - {self.balance_kwh} kWh"

    def has_sufficient_balance(self, amount_kwh: Decimal) -> bool:
        """Check if user has sufficient balance for charging."""
        return self.balance_kwh >= amount_kwh

    def deduct_balance(self, amount_kwh: Decimal) -> bool:
        """Deduct amount from balance. Returns True if successful."""
        if self.has_sufficient_balance(amount_kwh):
            self.balance_kwh -= amount_kwh
            self.save(update_fields=["balance_kwh", "updated_at"])
            return True
        return False

    def add_balance(self, amount_kwh: Decimal) -> None:
        """Add credits to user balance."""
        self.balance_kwh += amount_kwh
        self.save(update_fields=["balance_kwh", "updated_at"])
