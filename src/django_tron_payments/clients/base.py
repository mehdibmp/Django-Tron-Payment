"""Errors and data structures exposed by TRON network clients."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class TronClientError(Exception):
    """A recoverable or permanent hosted-TRON API failure."""


@dataclass(frozen=True)
class ObservedTransfer:
    """A normalized confirmed inbound transfer from the network index."""

    transaction_id: str
    event_index: int
    sender_address: str
    recipient_address: str
    amount_atomic: int
    observed_at: datetime
    raw_payload: dict
