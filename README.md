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

## Install

```bash
pip install django-tron-payments
```

Add the application to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_tron_payments",
]
```

Run migrations:

```bash
python manage.py migrate django_tron_payments
```

## Configuration

Keep all secrets outside source control. The following Nile-first example enables native TRX and one independently verified TRC-20 contract.

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
            "MINIMUM_DEPOSIT_ATOMIC": os.environ["MINIMUM_DEPOSIT_ATOMIC"],
        },
    ],
    "TRX_SWEEP_RESERVE_SUN": os.environ["TRX_SWEEP_RESERVE_SUN"],
    "TRC20_FEE_LIMIT_SUN": os.environ["TRC20_FEE_LIMIT_SUN"],
    "POLL_PAGE_SIZE": 100,
    "REQUEST_TIMEOUT_SECONDS": 15,
    "TASK_RETRY_LIMIT": 5,
}
```

TRX is always enabled; do not add it to `ASSETS`. Generate a Fernet key once, then place it in a secret manager:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For Mainnet, change `NETWORK` to `mainnet`, use Mainnet TronGrid credentials and verified contract addresses, and complete the security and Nile operations checks first.

## Celery

The app exposes shared Celery tasks. Run a worker and Beat process in the host project, then use this five-times-daily treasury sweep schedule:

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

Run a worker and Beat process separately:

```bash
celery -A your_project worker -l INFO
celery -A your_project beat -l INFO
```

A broadcast is never considered settled until `confirm_tron_sweeps` sees a successful confirmed receipt. When a worker loses the broadcast response after persisting a signed transaction ID, the sweep remains in a recovery state and must be reconciled before any manual decision.

## Application usage

```python
from django_tron_payments.services.wallets import public_wallet_address

address = public_wallet_address(user=request.user)
# `address` is the only wallet value safe to show to the user.
```

Never expose `encrypted_private_key`, encryption options, or backend credentials.

## TRC-20 sweep fees

A TRC-20 sender wallet needs TRX for bandwidth and energy. `TRC20_FEE_LIMIT_SUN` is the transaction fee ceiling and the minimum TRX balance required before the package queues a token sweep. Fund user deposit wallets with an approved operational process or implement a separately reviewed gas-sponsorship service. The package deliberately does not move treasury funds into user wallets automatically.

`TRX_SWEEP_RESERVE_SUN` keeps native TRX in each wallet, so a native sweep does not attempt to empty the account below its configured reserve.

## Operations

- Use `python manage.py reconcile_tron` for a controlled confirmed-transfer scan.
- Use `python manage.py sweep_tron` to queue, broadcast, or confirm controlled sweeps.
- Include `django_tron_payments.urls` in a staff-protected host URL configuration to use the dedicated operations console.
- Review deposits, sweep states, and audit details in Django admin.
- Read [docs/security.md](docs/security.md), [docs/operations.md](docs/operations.md), and [docs/configuration.md](docs/configuration.md) before enabling Mainnet.

## License

MIT. See [LICENSE](LICENSE).