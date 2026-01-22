from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models


class CreditTransaction(models.Model):
    """Records all credit transactions (additions and deductions)."""

    class TransactionType(models.TextChoices):
        ADMIN_CREDIT = "admin_credit", "Admin Credit"
        SESSION_DEBIT = "session_debit", "Session Debit"
        ADJUSTMENT = "adjustment", "Adjustment"
        REFUND = "refund", "Refund"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="credit_transactions")
    amount_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text="Positive for credit, negative for debit",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
    )
    session = models.ForeignKey(
        "stations.ChargingSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credits_added",
        help_text="Admin who added the credit",
    )
    description = models.CharField(max_length=255, blank=True)
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="User's balance after this transaction",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Credit Transaction"
        verbose_name_plural = "Credit Transactions"
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.amount_kwh >= 0 else ""
        return f"{self.user.username}: {sign}{self.amount_kwh} kWh ({self.transaction_type})"

    def save(self, *args, **kwargs):
        # Record balance after transaction
        if self.balance_after is None and hasattr(self.user, "profile"):
            self.balance_after = self.user.profile.balance_kwh
        super().save(*args, **kwargs)

    @classmethod
    def add_credit(cls, user, amount_kwh: Decimal, added_by=None, description: str = ""):
        """
        Add credits to a user's account.

        Args:
            user: The user to add credits to
            amount_kwh: Amount of credits in kWh
            added_by: Admin user who added the credits
            description: Optional description

        Returns:
            CreditTransaction: The created transaction
        """
        # Update user's balance
        profile = user.profile
        profile.add_balance(amount_kwh)

        # Create transaction record
        transaction = cls.objects.create(
            user=user,
            amount_kwh=amount_kwh,
            transaction_type=cls.TransactionType.ADMIN_CREDIT,
            added_by=added_by,
            description=description or "Credit added by admin",
            balance_after=profile.balance_kwh,
        )

        return transaction
