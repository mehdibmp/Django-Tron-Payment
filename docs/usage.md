# Usage Guide

This guide describes the public application interfaces already provided by `django-tron-payments`. It assumes Django settings, the TronGrid API key, encryption backend, treasury address, migrations, and Celery have already been configured as described in [configuration.md](configuration.md).

## 1. Mount the staff operations console

In the host project URL configuration:

```python
from django.urls import include, path

urlpatterns = [
    path("tron-operations/", include("django_tron_payments.urls")),
]
```

The resulting dashboard is `/tron-operations/`. Both dashboard and operation endpoints require a logged-in staff user. Keep the mount behind the host project’s normal HTTPS, authentication, and administrative access controls.

## 2. Create or retrieve a user wallet

```python
from django_tron_payments.services.wallets import get_or_create_wallet

wallet = get_or_create_wallet(user=request.user)
public_address = wallet.address
```

The operation is idempotent for one user and network. To return only the safe public value:

```python
from django_tron_payments.services.wallets import public_wallet_address

public_address = public_wallet_address(user=request.user)
```

Never serialize `encrypted_private_key` or pass the `ManagedWallet` object directly to an untrusted serializer.

## 3. Read a wallet balance

The client returns integer atomic units and performs a network/API balance lookup. Use SUN for TRX; do not convert through floating-point arithmetic.

```python
from django_tron_payments.clients.trongrid import TronGridClient
from django_tron_payments.conf import get_tron_settings
from django_tron_payments.services.wallets import get_or_create_wallet

configured = get_tron_settings()
wallet = get_or_create_wallet(user=request.user)
client = TronGridClient(configured)

trx_balance_sun = client.get_trx_balance_sun(wallet.address)

usdt = configured.asset("USDT")
usdt_balance_atomic = client.get_trc20_balance(wallet.address, usdt)
```

`configured.asset("USDT")` only works when USDT is present in `TRON_PAYMENTS["ASSETS"]`. Validate that the wallet belongs to the requesting user and that its network equals `configured.network` before returning a balance. Apply the host project’s timeout, rate-limit, and caching policy around user-facing balance requests.

## 4. List successful inbound transactions

Confirmed inbound transfers persisted by reconciliation are available in `IncomingPayment`. The query below returns only successful records for the selected wallet:

```python
from django_tron_payments.constants import PaymentStatus
from django_tron_payments.models import IncomingPayment

successful_payments = IncomingPayment.objects.filter(
    wallet=wallet,
    status=PaymentStatus.CONFIRMED,
).order_by("-confirmed_at")
```

Useful fields are `asset_code`, `asset_kind`, `amount_atomic`, `transaction_id`, `sender_address`, `recipient_address`, `observed_at`, and `confirmed_at`. Paginate this queryset in a user-facing view. The package records a payment only after the client reports the transfer as confirmed and applies an idempotency key based on network, asset, transaction ID, and event index.

To trigger a controlled reconciliation scan:

```bash
python manage.py reconcile_tron
```

The scan covers active wallets on the configured network and configured assets. It does not expose private keys.

## 5. List successful treasury sweeps

Successful outbound transfers for a wallet are stored as confirmed `TreasurySweep` records:

```python
from django_tron_payments.constants import SweepStatus
from django_tron_payments.models import TreasurySweep

successful_sweeps = TreasurySweep.objects.filter(
    wallet=wallet,
    status=SweepStatus.CONFIRMED,
).order_by("-confirmed_at")
```

Use `transaction_id` to link a confirmed sweep to a trusted network explorer. Do not treat `queued`, `building`, or `broadcast` as final success.

## 6. Sweep lifecycle and fee failure reason

Run the lifecycle manually only for controlled operations:

```bash
python manage.py sweep_tron queue
python manage.py sweep_tron broadcast
python manage.py sweep_tron confirm
# Or run the three stages sequentially:
python manage.py sweep_tron all
```

For a TRC-20 asset, the queue stage reads the wallet’s TRX balance before creating `TreasurySweep`. If the balance is below `TRC20_FEE_LIMIT_SUN`:

- no token sweep record is created;
- no token transfer is broadcast;
- a `PaymentAuditEvent` with `event_type="sweep.skipped"` is recorded;
- its metadata contains `reason="insufficient_trx_for_fee"`, `asset_code`, `trx_balance_sun`, and `required_trx_sun`;
- the same unchanged condition does not create duplicate audit events.

Review these conditions in the operations dashboard or the Payment audit events section of Django admin. After funding the wallet with enough TRX, run the queue stage again; the token sweep can then be planned if its token balance meets `MINIMUM_DEPOSIT_ATOMIC`.

## 7. Production safety checklist

- Use Nile and test funds before Mainnet.
- Verify the network, treasury address, API key, and token contracts independently.
- Keep private-key encryption keys outside source control and restrict worker access.
- Require staff authorization for the operations console.
- Monitor `sweep.skipped`, `failed`, `building`, and stale `broadcast` conditions.
- Confirm receipts before treating an outbound transfer as settled.
