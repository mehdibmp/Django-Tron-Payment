# django-tron-payments

A reusable, custodial Django application for receiving and sweeping TRX and configured TRC-20 token deposits through hosted TronGrid APIs. It does not operate a TRON node.

> **Security notice:** This package controls private keys. Use Nile before Mainnet, protect encryption keys with a KMS/HSM in production, review local custody and financial-regulation obligations, and arrange independent security review before handling real funds.

## Features

- Creates one encrypted custodial deposit wallet for each Django user.
- Shows applications only a user wallet's public TRON address.
- Monitors confirmed TRX and configured TRC-20 transfers through TronGrid.
- Records idempotent deposit and sweep audit trails.
- Sweeps eligible balances to one configured treasury address on a Celery Beat schedule.
- Provides dedicated, staff-only Django admin pages and management commands.
- Supports a Fernet/MultiFernet development backend and a pluggable KMS/HSM-compatible encryption interface.

## Requirements

- Python 3.12+
- Django 5.1+
- Celery 5.4+ with a configured broker and result backend
- Redis is recommended for Celery
- A TronGrid API key

## Install and bootstrap

Before running migrations, complete the following prerequisites:

1. Create a TronGrid account and obtain an API key for the network you will use. Keep the key in a secret manager or environment variable; never commit it.
2. Create or select a treasury address on that same network. Verify the address independently and do not use a managed deposit address as the treasury.
3. Generate the wallet-encryption key and store it securely. For a development Fernet key:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. Install the package and its host-project dependencies:

   ```bash
   pip install django-tron-payments
   ```

5. Add the application to `INSTALLED_APPS`:

   ```python
   INSTALLED_APPS = [
       # ...
       "django_tron_payments",
   ]
   ```

6. Add the `TRON_PAYMENTS` settings shown below. The API key, treasury address, encryption key, and token contract addresses must be valid for the selected network.
7. Run Django checks and then apply the package migrations:

   ```bash
   python manage.py check
   python manage.py migrate
   ```

8. Include `django_tron_payments.urls` from a host-project URL configuration. The operations views enforce staff access, but the host project should still place them behind its normal administrative URL policy.
9. Configure the Celery worker, broker, result backend, and Beat schedule described below. Run reconciliation before expecting confirmed deposits or sweeps to appear.

Do not move to Mainnet until the complete flow has been tested on Nile with test funds and independently reviewed.
## Configuration

Keep all secrets outside source control. The following Nile-first example enables native TRX and one independently verified TRC-20 contract. Numeric settings must be Python integers; environment variables therefore need explicit `int(...)` conversion.

```python
import os

TRON_PAYMENTS = {
    "NETWORK": "nile",
    "TRONGRID_API_KEY": os.environ["TRONGRID_API_KEY"],
    "TREASURY_ADDRESS": os.environ["TRON_TREASURY_ADDRESS"],
    "ENCRYPTION_BACKEND": "django_tron_payments.crypto.fernet.FernetKeyCipher",
    "ENCRYPTION_OPTIONS": {
        "FERNET_KEYS": [os.environ["TRON_WALLET_ENCRYPTION_KEY"]],
    },
    "ASSETS": [
        {
            "CODE": "USDT",
            "KIND": "TRC20",
            "CONTRACT_ADDRESS": os.environ["NILE_USDT_CONTRACT_ADDRESS"],
            "DECIMALS": 6,
            "MINIMUM_DEPOSIT_ATOMIC": int(os.environ["MINIMUM_DEPOSIT_ATOMIC"]),
        },
    ],
    "TRX_SWEEP_RESERVE_SUN": int(os.environ.get("TRX_SWEEP_RESERVE_SUN", "1000000")),
    "TRC20_FEE_LIMIT_SUN": int(os.environ.get("TRC20_FEE_LIMIT_SUN", "3000000")),
    "POLL_PAGE_SIZE": 100,
    "REQUEST_TIMEOUT_SECONDS": 15,
    "TASK_RETRY_LIMIT": 5,
}
```

TRX is always enabled; do not add it to `ASSETS`. TRX uses 6 decimal places and SUN atomic units (`1 TRX = 1,000,000 SUN`). For each TRC-20 asset, independently verify the contract address, decimals, and minimum amount for the selected network. A token symbol alone is not a safe identity.

For Mainnet, change `NETWORK` to `mainnet`, use Mainnet TronGrid credentials and verified contract addresses, and complete the security and Nile operations checks first.

After changing settings, run:

```bash
python manage.py check
python manage.py migrate
```

## Celery and scheduled lifecycle

The package exposes shared Celery tasks, but the host project must provide a configured broker, result backend, worker, and Beat scheduler. Run one Beat scheduler instance only.

Configure a schedule in the host project after the Django settings and migrations are ready:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "tron-reconcile": {
        "task": "django_tron_payments.tasks.reconcile_tron_payments",
        "schedule": 300.0,
    },
    "tron-queue-sweeps": {
        "task": "django_tron_payments.tasks.queue_tron_sweeps",
        "schedule": crontab(minute=0, hour="0,5,10,14,19"),
    },
    "tron-broadcast-sweeps": {
        "task": "django_tron_payments.tasks.broadcast_tron_sweeps",
        "schedule": crontab(minute=2, hour="0,5,10,14,19"),
    },
    "tron-confirm-sweeps": {
        "task": "django_tron_payments.tasks.confirm_tron_sweeps",
        "schedule": 300.0,
    },
}
```

Run the worker and Beat process separately from the host project:

```bash
celery -A your_project worker -l INFO
celery -A your_project beat -l INFO
```

The lifecycle is: reconcile confirmed deposits, check balances and plan eligible sweeps, broadcast queued transfers, then confirm successful receipts. A broadcast is never considered settled until `confirm_tron_sweeps` sees a successful confirmed receipt. If the worker loses the broadcast response after persisting a signed transaction ID, the sweep remains in a recovery state and must be reconciled before any manual decision.

## Application usage

The package exposes services and models rather than an unauthenticated end-user API. Add your own authenticated views or service layer in the host project and authorize access to the requested user before returning any wallet or payment data. See [docs/usage.md](docs/usage.md) for complete examples.

```python
from django_tron_payments.services.wallets import public_wallet_address

address = public_wallet_address(user=request.user)
# Only the public address is safe to show to the wallet owner.
```

Never expose `encrypted_private_key`, encryption options, API keys, or encryption-backend credentials. Amounts returned by the client and stored by the models are integer atomic units: SUN for TRX and the configured smallest unit for a TRC-20 asset.

## TRC-20 sweep fees

A TRC-20 sender wallet needs TRX for bandwidth and energy. `TRC20_FEE_LIMIT_SUN` is the transaction fee ceiling and the minimum TRX balance required before the package queues a token sweep. If the wallet is below this amount, the token sweep is not created or placed in `TreasurySweep`; a `sweep.skipped` audit event records the asset, current TRX balance, required balance, and reason `insufficient_trx_for_fee`. Repeated checks with the same values are idempotent. Review these events in the operations dashboard or Django admin.

Fund user deposit wallets with an approved operational process or implement a separately reviewed gas-sponsorship service. The package deliberately does not move treasury funds into user wallets automatically.

`TRX_SWEEP_RESERVE_SUN` keeps native TRX in each wallet, so a native sweep does not attempt to empty the account below its configured reserve.

## Operations

- Use `python manage.py reconcile_tron` for a controlled confirmed-transfer scan.
- Use `python manage.py sweep_tron queue`, `broadcast`, `confirm`, or `all` for controlled sweep lifecycle actions.
- Include `django_tron_payments.urls` in a staff-protected host URL configuration to use the operations console.
- Review wallets, confirmed payments, sweep states, and `sweep.skipped` audit events in Django admin.
- Read [docs/usage.md](docs/usage.md), [docs/security.md](docs/security.md), [docs/operations.md](docs/operations.md), and [docs/configuration.md](docs/configuration.md) before enabling Mainnet.

## License

MIT. See [LICENSE](LICENSE).
