"""Constants shared by models, services, and tasks."""

from django.db.models import TextChoices


SUN_PER_TRX = 1_000_000


class WalletStatus(TextChoices):
    ACTIVE = "active", "Active"
    DISABLED = "disabled", "Disabled"


class PaymentStatus(TextChoices):
    OBSERVED = "observed", "Observed"
    CONFIRMED = "confirmed", "Confirmed"
    FAILED = "failed", "Failed"


class SweepStatus(TextChoices):
    QUEUED = "queued", "Queued"
    BUILDING = "building", "Building"
    BROADCAST = "broadcast", "Broadcast"
    CONFIRMED = "confirmed", "Confirmed"
    FAILED = "failed", "Failed"


ACTIVE_SWEEP_STATUSES = (SweepStatus.QUEUED, SweepStatus.BUILDING, SweepStatus.BROADCAST)
