# Generated manually for django-tron-payments.

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="ManagedWallet",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("network", models.CharField(db_index=True, max_length=16)),
                ("address", models.CharField(db_index=True, max_length=64)),
                ("encrypted_private_key", models.TextField(editable=False)),
                ("encryption_backend", models.CharField(editable=False, max_length=255)),
                ("status", models.CharField(choices=[("active", "Active"), ("disabled", "Disabled")], db_index=True, default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tron_payment_wallets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="TreasurySweep",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("network", models.CharField(db_index=True, max_length=16)),
                ("asset_code", models.CharField(db_index=True, max_length=32)),
                ("asset_kind", models.CharField(max_length=16)),
                ("token_contract_address", models.CharField(blank=True, max_length=64)),
                ("destination_address", models.CharField(max_length=64)),
                ("amount_atomic", models.BigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("fee_limit_sun", models.BigIntegerField(default=0)),
                ("transaction_id", models.CharField(blank=True, db_index=True, max_length=128)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("building", "Building"), ("broadcast", "Broadcast"), ("confirmed", "Confirmed"), ("failed", "Failed")], db_index=True, default="queued", max_length=16)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, max_length=500)),
                ("broadcast_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="treasury_sweeps", to="django_tron_payments.managedwallet")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="IncomingPayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("network", models.CharField(db_index=True, max_length=16)),
                ("asset_code", models.CharField(db_index=True, max_length=32)),
                ("asset_kind", models.CharField(max_length=16)),
                ("token_contract_address", models.CharField(blank=True, max_length=64)),
                ("transaction_id", models.CharField(db_index=True, max_length=128)),
                ("event_index", models.PositiveIntegerField(default=0)),
                ("sender_address", models.CharField(max_length=64)),
                ("recipient_address", models.CharField(max_length=64)),
                ("amount_atomic", models.BigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("observed_at", models.DateTimeField()),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("observed", "Observed"), ("confirmed", "Confirmed"), ("failed", "Failed")], db_index=True, default="observed", max_length=16)),
                ("raw_payload", models.JSONField(default=dict, editable=False)),
                ("failure_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_payments", to="django_tron_payments.managedwallet")),
            ],
            options={"ordering": ("-observed_at",)},
        ),
        migrations.CreateModel(
            name="PaymentAuditEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("message", models.CharField(max_length=500)),
                ("metadata", models.JSONField(default=dict, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("incoming_payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="django_tron_payments.incomingpayment")),
                ("treasury_sweep", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="django_tron_payments.treasurysweep")),
                ("wallet", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="django_tron_payments.managedwallet")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(model_name="managedwallet", constraint=models.UniqueConstraint(fields=("user", "network"), name="tron_payments_one_wallet_per_user_network")),
        migrations.AddConstraint(model_name="managedwallet", constraint=models.UniqueConstraint(fields=("network", "address"), name="tron_payments_unique_network_address")),
        migrations.AddConstraint(model_name="incomingpayment", constraint=models.UniqueConstraint(fields=("network", "asset_code", "transaction_id", "event_index"), name="tron_payments_unique_incoming_transfer")),
        migrations.AddIndex(model_name="managedwallet", index=models.Index(fields=["network", "status"], name="django_tron_network_9b44f1_idx")),
        migrations.AddIndex(model_name="incomingpayment", index=models.Index(fields=["network", "status", "asset_code"], name="django_tron_network_5efdd7_idx")),
        migrations.AddIndex(model_name="incomingpayment", index=models.Index(fields=["wallet", "status"], name="django_tron_wallet__7eeb74_idx")),
        migrations.AddIndex(model_name="treasurysweep", index=models.Index(fields=["network", "status", "asset_code"], name="django_tron_network_67fc89_idx")),
        migrations.AddIndex(model_name="treasurysweep", index=models.Index(fields=["wallet", "status"], name="django_tron_wallet__1b6504_idx")),
    ]
