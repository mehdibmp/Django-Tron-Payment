"""Staff-only operations console views."""

from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django_tron_payments.conf import get_tron_settings
from django_tron_payments.constants import PaymentStatus, SweepStatus
from django_tron_payments.models import (
    IncomingPayment,
    ManagedWallet,
    PaymentAuditEvent,
    TreasurySweep,
)
from django_tron_payments.tasks import (
    broadcast_tron_sweeps,
    confirm_tron_sweeps,
    queue_tron_sweeps,
    reconcile_tron_payments,
)


_OPERATION_TASKS = {
    "reconcile": (reconcile_tron_payments, "Deposit reconciliation was queued."),
    "queue-sweeps": (queue_tron_sweeps, "Treasury sweep planning was queued."),
    "broadcast-sweeps": (broadcast_tron_sweeps, "Queued treasury sweeps were queued for broadcast."),
    "confirm-sweeps": (confirm_tron_sweeps, "Sweep receipt confirmation was queued."),
}


@staff_member_required
def operations_dashboard(request):
    """Present non-secret operational health and recent payment activity."""
    configured = get_tron_settings()
    stale_before = timezone.now() - timedelta(hours=24)
    confirmed_payments = IncomingPayment.objects.filter(status=PaymentStatus.CONFIRMED)
    fee_skipped_events = PaymentAuditEvent.objects.filter(
        wallet__network=configured.network,
        event_type="sweep.skipped",
        metadata__reason="insufficient_trx_for_fee",
    ).select_related("wallet").order_by("-created_at")
    context = {
        "title": "TRON payment operations",
        "configured": configured,
        "wallet_count": ManagedWallet.objects.filter(network=configured.network).count(),
        "confirmed_payment_count": confirmed_payments.filter(network=configured.network).count(),
        "confirmed_payment_total": confirmed_payments.filter(network=configured.network).aggregate(
            total=Sum("amount_atomic")
        )["total"]
        or 0,
        "pending_sweep_count": TreasurySweep.objects.filter(
            network=configured.network,
            status__in=(SweepStatus.QUEUED, SweepStatus.BUILDING, SweepStatus.BROADCAST),
        ).count(),
        "failed_sweep_count": TreasurySweep.objects.filter(
            network=configured.network,
            status=SweepStatus.FAILED,
        ).count(),
        "stale_broadcast_count": TreasurySweep.objects.filter(
            network=configured.network,
            status__in=(SweepStatus.BUILDING, SweepStatus.BROADCAST),
            updated_at__lt=stale_before,
        ).count(),
        "insufficient_trx_event_count": fee_skipped_events.count(),
        "recent_insufficient_trx_events": fee_skipped_events[:10],
        "recent_payments": confirmed_payments.filter(network=configured.network).select_related(
            "wallet", "wallet__user"
        )[:10],
        "recent_sweeps": TreasurySweep.objects.filter(network=configured.network).select_related(
            "wallet", "wallet__user"
        )[:10],
        "asset_summary": confirmed_payments.filter(network=configured.network)
        .values("asset_code")
        .annotate(count=Count("id"), total=Sum("amount_atomic"))
        .order_by("asset_code"),
    }
    return render(request, "django_tron_payments/operations/dashboard.html", context)


@require_POST
@staff_member_required
def run_operation(request, operation: str):
    """Queue one approved, non-destructive background operation from the console."""
    task_definition = _OPERATION_TASKS.get(operation)
    if task_definition is None:
        messages.error(request, "The requested TRON operation is not available.")
        return redirect("django_tron_payments:operations-dashboard")

    task, success_message = task_definition
    task.delay()
    messages.success(request, success_message)
    return redirect("django_tron_payments:operations-dashboard")
