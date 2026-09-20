"""Celery tasks for confirmed deposit reconciliation and treasury operations."""

from __future__ import annotations

from celery import shared_task

from django_tron_payments.clients.base import TronClientError
from django_tron_payments.conf import get_tron_settings
from django_tron_payments.services.deposits import reconcile_active_wallets
from django_tron_payments.services.sweeps import (
    broadcast_queued_sweeps,
    confirm_broadcast_sweeps,
    queue_sweeps,
)


@shared_task(
    bind=True,
    autoretry_for=(TronClientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=240,
    time_limit=300,
)
def reconcile_tron_payments(self) -> int:
    """Record configured inbound transfers from TronGrid-confirmed data."""
    self.max_retries = get_tron_settings().task_retry_limit
    return reconcile_active_wallets()


@shared_task(
    bind=True,
    autoretry_for=(TronClientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=240,
    time_limit=300,
)
def queue_tron_sweeps(self) -> int:
    """Create idempotent sweep records for balances eligible for transfer."""
    self.max_retries = get_tron_settings().task_retry_limit
    return queue_sweeps()


@shared_task(soft_time_limit=300, time_limit=360)
def broadcast_tron_sweeps() -> int:
    """Build, sign, persist, and broadcast queued treasury sweep transactions."""
    return broadcast_queued_sweeps()


@shared_task(
    bind=True,
    autoretry_for=(TronClientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=240,
    time_limit=300,
)
def confirm_tron_sweeps(self) -> int:
    """Move submitted sweeps to confirmed only after a successful receipt."""
    self.max_retries = get_tron_settings().task_retry_limit
    return confirm_broadcast_sweeps()
