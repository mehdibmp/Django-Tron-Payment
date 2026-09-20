from django_tron_payments.tasks import (
    broadcast_tron_sweeps,
    confirm_tron_sweeps,
    queue_tron_sweeps,
    reconcile_tron_payments,
)


def test_celery_task_names_are_stable_for_beat_configuration():
    assert reconcile_tron_payments.name == "django_tron_payments.tasks.reconcile_tron_payments"
    assert queue_tron_sweeps.name == "django_tron_payments.tasks.queue_tron_sweeps"
    assert broadcast_tron_sweeps.name == "django_tron_payments.tasks.broadcast_tron_sweeps"
    assert confirm_tron_sweeps.name == "django_tron_payments.tasks.confirm_tron_sweeps"
