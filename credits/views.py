from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import CreditTransaction


@login_required
def transaction_history(request):
    """View user's credit transaction history."""
    transactions = CreditTransaction.objects.filter(user=request.user).order_by("-created_at")

    # Calculate totals
    total_credits = sum(t.amount_kwh for t in transactions if t.amount_kwh > 0)
    total_debits = sum(t.amount_kwh for t in transactions if t.amount_kwh < 0)

    context = {
        "transactions": transactions,
        "total_credits": total_credits,
        "total_debits": abs(total_debits),
        "current_balance": request.user.profile.balance_kwh,
    }
    return render(request, "credits/transaction_history.html", context)
