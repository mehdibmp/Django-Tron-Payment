"""Persistent custodial wallet, payment, sweep, and audit records."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from django_tron_payments.constants import PaymentStatus, SweepStatus, WalletStatus


class ManagedWallet(models.Model):
    """A custodial TRON address associated with one host-project user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tron_payment_wallets",
    )
    network = models.CharField(max_length=16, db_index=True)
    address = models.CharField(max_length=64, db_index=True)
    encrypted_private_key = models.TextField(editable=False)
    encryption_backend = models.CharField(max_length=255, editable=False)
    status = models.CharField(
        max_length=16,
        choices=WalletStatus.choices,
        default=WalletStatus.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "network"),
                name="tron_payments_one_wallet_per_user_network",
            ),
            models.UniqueConstraint(
                fields=("network", "address"),
                name="tron_payments_unique_network_address",
            ),
        ]
        indexes = [models.Index(fields=("network", "status"))]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.address} ({self.network})"


class IncomingPayment(models.Model):
    """An inbound native-TRX or configured TRC-20 transfer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        ManagedWallet,
        on_delete=models.PROTECT,
        related_name="incoming_payments",
    )
    network = models.CharField(max_length=16, db_index=True)
    asset_code = models.CharField(max_length=32, db_index=True)
    asset_kind = models.CharField(max_length=16)
    token_contract_address = models.CharField(max_length=64, blank=True)
    transaction_id = models.CharField(max_length=128, db_index=True)
    event_index = models.PositiveIntegerField(default=0)
    sender_address = models.CharField(max_length=64)
    recipient_address = models.CharField(max_length=64)
    amount_atomic = models.BigIntegerField(validators=(MinValueValidator(1),))
    observed_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.OBSERVED,
        db_index=True,
    )
    raw_payload = models.JSONField(default=dict, editable=False)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("network", "asset_code", "transaction_id", "event_index"),
                name="tron_payments_unique_incoming_transfer",
            )
        ]
        indexes = [
            models.Index(fields=("network", "status", "asset_code")),
            models.Index(fields=("wallet", "status")),
        ]
        ordering = ("-observed_at",)

    def __str__(self) -> str:
        return f"{self.asset_code} payment {self.transaction_id}"

    def mark_confirmed(self) -> None:
        """Move an observed payment into its terminal confirmed state."""
        self.status = PaymentStatus.CONFIRMED
        self.confirmed_at = timezone.now()
        self.failure_reason = ""
        self.save(update_fields=("status", "confirmed_at", "failure_reason", "updated_at"))


class TreasurySweep(models.Model):
    """A planned or executed transfer from one managed wallet to the treasury."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        ManagedWallet,
        on_delete=models.PROTECT,
        related_name="treasury_sweeps",
    )
    network = models.CharField(max_length=16, db_index=True)
    asset_code = models.CharField(max_length=32, db_index=True)
    asset_kind = models.CharField(max_length=16)
    token_contract_address = models.CharField(max_length=64, blank=True)
    destination_address = models.CharField(max_length=64)
    amount_atomic = models.BigIntegerField(validators=(MinValueValidator(1),))
    fee_limit_sun = models.BigIntegerField(default=0)
    transaction_id = models.CharField(max_length=128, blank=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=SweepStatus.choices,
        default=SweepStatus.QUEUED,
        db_index=True,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    broadcast_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("network", "status", "asset_code")),
            models.Index(fields=("wallet", "status")),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.asset_code} sweep {self.id}"


class PaymentAuditEvent(models.Model):
    """Append-only operational record that deliberately excludes private keys."""

    id = models.BigAutoField(primary_key=True)
    wallet = models.ForeignKey(
        ManagedWallet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    incoming_payment = models.ForeignKey(
        IncomingPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    treasury_sweep = models.ForeignKey(
        TreasurySweep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    event_type = models.CharField(max_length=64, db_index=True)
    message = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.event_type} at {self.created_at:%Y-%m-%d %H:%M:%S}"
