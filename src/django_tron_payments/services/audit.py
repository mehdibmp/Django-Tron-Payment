"""Non-secret audit event helpers."""

from __future__ import annotations

from typing import Any

from django_tron_payments.models import PaymentAuditEvent


def record_event(
    *,
    event_type: str,
    message: str,
    wallet=None,
    incoming_payment=None,
    treasury_sweep=None,
    **context: Any,
) -> PaymentAuditEvent:
    """Store an operational event after callers have removed all secrets."""
    return PaymentAuditEvent.objects.create(
        event_type=event_type,
        message=message,
        wallet=wallet,
        incoming_payment=incoming_payment,
        treasury_sweep=treasury_sweep,
        metadata=context,
    )