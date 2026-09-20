"""Manually queue, broadcast, and confirm treasury sweeps."""

from django.core.management.base import BaseCommand, CommandError

from django_tron_payments.services.sweeps import (
    broadcast_queued_sweeps,
    confirm_broadcast_sweeps,
    queue_sweeps,
)


class Command(BaseCommand):
    """Perform one explicit treasury-sweep lifecycle action."""

    help = "Queue, broadcast, or confirm TRON treasury sweeps."

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=("queue", "broadcast", "confirm", "all"),
            help="Lifecycle action to execute.",
        )

    def handle(self, *args, **options):
        del args
        action = options["action"]
        if action == "queue":
            self.stdout.write(f"Queued {queue_sweeps()} sweep(s).")
            return
        if action == "broadcast":
            self.stdout.write(f"Broadcast {broadcast_queued_sweeps()} sweep(s).")
            return
        if action == "confirm":
            self.stdout.write(f"Confirmed {confirm_broadcast_sweeps()} sweep(s).")
            return
        if action != "all":
            raise CommandError("Unsupported sweep action.")
        queued = queue_sweeps()
        broadcast = broadcast_queued_sweeps()
        confirmed = confirm_broadcast_sweeps()
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued {queued}, broadcast {broadcast}, and confirmed {confirmed} sweep(s)."
            )
        )
