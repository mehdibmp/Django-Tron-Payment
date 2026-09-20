# Configuration Reference

`django-tron-payments` is a custodial-payment package. All secret values belong in a secret manager or environment-derived settings module, never in source control.

## Required settings

```python
TRON_PAYMENTS = {
    "NETWORK": "nile",
    "TRONGRID_API_KEY": os.environ["TRONGRID_API_KEY"],
    "TREASURY_ADDRESS": os.environ["TRON_TREASURY_ADDRESS"],
    "ENCRYPTION_BACKEND": "django_tron_payments.crypto.fernet.FernetKeyCipher",
    "ENCRYPTION_OPTIONS": {"FERNET_KEYS": [os.environ["TRON_KEY_ENCRYPTION_KEY"]]},
    "ASSETS": [
        {
            "CODE": "USDT",
            "KIND": "TRC20",
            "CONTRACT_ADDRESS": os.environ["NILE_USDT_CONTRACT_ADDRESS"],
            "DECIMALS": 6,
            "MINIMUM_DEPOSIT_ATOMIC": 1_000_000,
        },
    ],
}
```

TRX is always supported and uses 6 decimal places / SUN atomic units. Add only token contracts you have independently verified for the selected network. A token symbol alone is not a safe identity.

## Key-custody backends

The default Fernet backend accepts an ordered `FERNET_KEYS` list. The first key encrypts new wallets; all keys may decrypt existing wallets, enabling staged key rotation.

For KMS/HSM custody, point `ENCRYPTION_BACKEND` at an importable class that implements:

```python
class CustomKeyCipher:
    def encrypt(self, plaintext: bytes) -> str: ...
    def decrypt(self, token: str) -> bytes: ...
```

The custom backend must use authenticated encryption, restrict decryption authority to Celery workers that need it, never log plaintext, and implement tested key rotation.

## Celery Beat

Use a schedule such as:

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

The sweep schedule runs five times per day. The explicit receipt-confirmation task runs more frequently, including after an ambiguous broadcast response.

## Fee policies

`TRX_SWEEP_RESERVE_SUN` keeps native TRX in each wallet to fund outbound transactions. `TRC20_FEE_LIMIT_SUN` is both a per-token-transfer fee ceiling and the minimum TRX balance required before the package queues a token sweep. Fund deposit wallets with TRX deliberately or operate an approved gas-sponsorship mechanism outside this package.
