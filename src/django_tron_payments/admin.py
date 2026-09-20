"""Safe Django-admin integration for TRON payment operations."""

from __future__ import annotations

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from django_tron_payments.models import (
    IncomingPayment,
    ManagedWallet,
    PaymentAuditEvent,
    TreasurySweep,
)


class PaymentAuditInline(admin.TabularInline):
    """Base inline for immutable, parent-specific payment audit events."""

    model = PaymentAuditEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "message", "metadata", "created_at")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class WalletAuditInline(PaymentAuditInline):
    fk_name = "wallet"


class IncomingPaymentAuditInline(PaymentAuditInline):
    fk_name = "incoming_payment"


class TreasurySweepAuditInline(PaymentAuditInline):
    fk_name = "treasury_sweep"


@admin.register(ManagedWallet)
class ManagedWalletAdmin(admin.ModelAdmin):
    change_list_template = "django_tron_payments/admin/wallet_change_list.html"
    list_display = ("address", "user", "network", "status", "created_at")
    list_filter = ("network", "status")
    search_fields = ("address", "user__username", "user__email")
    readonly_fields = (
        "id",
        "user",
        "network",
        "address",
        "encryption_backend",
        "status",
        "created_at",
        "updated_at",
    )
    exclude = ("encrypted_private_key",)
    inlines = (WalletAuditInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IncomingPayment)
class IncomingPaymentAdmin(admin.ModelAdmin):
    change_list_template = "django_tron_payments/admin/payment_change_list.html"
    list_display = (
        "transaction_link",
        "wallet",
        "asset_code",
        "amount_atomic",
        "sender_address",
        "status",
        "confirmed_at",
    )
    list_filter = ("network", "asset_code", "asset_kind", "status")
    search_fields = ("transaction_id", "sender_address", "recipient_address", "wallet__address")
    readonly_fields = (
        "id",
        "wallet",
        "network",
        "asset_code",
        "asset_kind",
        "token_contract_address",
        "transaction_id",
        "event_index",
        "sender_address",
        "recipient_address",
        "amount_atomic",
        "observed_at",
        "confirmed_at",
        "status",
        "raw_payload",
        "failure_reason",
        "created_at",
        "updated_at",
    )
    inlines = (IncomingPaymentAuditInline,)

    @admin.display(description="Transaction")
    def transaction_link(self, obj):
        url = f"https://nile.tronscan.org/#/transaction/{obj.transaction_id}"
        if obj.network == "mainnet":
            url = f"https://tronscan.org/#/transaction/{obj.transaction_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, obj.transaction_id[:16])

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TreasurySweep)
class TreasurySweepAdmin(admin.ModelAdmin):
    change_list_template = "django_tron_payments/admin/sweep_change_list.html"
    list_display = ("id", "wallet", "asset_code", "amount_atomic", "status", "transaction_id", "updated_at")
    list_filter = ("network", "asset_code", "asset_kind", "status")
    search_fields = ("transaction_id", "wallet__address", "destination_address")
    readonly_fields = (
        "id",
        "wallet",
        "network",
        "asset_code",
        "asset_kind",
        "token_contract_address",
        "destination_address",
        "amount_atomic",
        "fee_limit_sun",
        "transaction_id",
        "status",
        "attempt_count",
        "last_error",
        "broadcast_at",
        "confirmed_at",
        "created_at",
        "updated_at",
    )
    inlines = (TreasurySweepAuditInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentAuditEvent)
class PaymentAuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "message", "wallet", "incoming_payment", "treasury_sweep", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("message", "wallet__address", "incoming_payment__transaction_id", "treasury_sweep__transaction_id")
    readonly_fields = ("event_type", "message", "metadata", "wallet", "incoming_payment", "treasury_sweep", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def operations_console_url() -> str:
    """Return the named route so host admin templates can link to the console."""
    return reverse("django_tron_payments:operations-dashboard")
