# Configuration Reference

`django-tron-payments` is a custodial-payment package. Complete the prerequisites and set the selected network before running migrations or creating wallets. Keep every secret in a secret manager or environment-derived settings module, never in source control.

## 1. Prerequisites before migration

1. Create a TronGrid account and obtain an API key for the selected network.
2. Create and independently verify a treasury address on that same network.
3. Verify every TRC-20 contract address and its decimals for that network.
4. Generate and securely store the wallet-encryption key. For development-only Fernet setup:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

5. Configure the settings below, then run `python manage.py check`.
6. Only after the checks pass, run `python manage.py migrate`.

## 2. Required settings

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
            "MINIMUM_DEPOSIT_ATOMIC": 1_000_000,
        },
    ],
    "TRX_SWEEP_RESERVE_SUN": 1_000_000,
    "TRC20_FEE_LIMIT_SUN": 3_000_000,
    "POLL_PAGE_SIZE": 100,
    "REQUEST_TIMEOUT_SECONDS": 15,
    "TASK_RETRY_LIMIT": 5,
}
```

`TRON_PAYMENTS` must be a dictionary. `NETWORK` must be `nile`, `shasta`, or `mainnet`. `TRONGRID_API_KEY` and `TREASURY_ADDRESS` are required strings. Numeric values must be Python integers; use `int(os.environ[...])` when reading numeric environment variables. TRX is always enabled and must not be repeated in `ASSETS`.

TRX uses six decimal places and SUN atomic units: `1 TRX = 1,000,000 SUN`. A TRC-20 amount uses the smallest unit defined by its configured `DECIMALS`. The contract address, decimals, and minimum amount must be verified independently for the selected network.

## 3. Key custody

The default Fernet backend accepts an ordered `FERNET_KEYS` list. The first key encrypts new wallets; all keys may decrypt existing wallets, which supports staged rotation. For production, use a reviewed KMS/HSM-compatible backend:

```python
class CustomKeyCipher:
    def encrypt(self, plaintext: bytes) -> str: ...
    def decrypt(self, token: str) -> bytes: ...
```

The backend must use authenticated encryption, restrict decryption authority to workers that need it, never log plaintext or private keys, and implement tested key rotation and recovery procedures.

## 4. Celery Beat

Configure the host project after Django settings and migrations are ready. Run one Beat scheduler instance only:

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

Start the host worker and Beat separately:

```bash
celery -A your_project worker -l INFO
celery -A your_project beat -l INFO
```

## 5. Fee and reserve policy

`TRX_SWEEP_RESERVE_SUN` is retained when sweeping native TRX. `TRC20_FEE_LIMIT_SUN` is both the TRC-20 transaction fee ceiling and the minimum TRX balance required for token sweep planning. If a token wallet is below that threshold, no `TreasurySweep` is created; the service records one idempotent `sweep.skipped` audit event for the current balance/threshold pair. The operations dashboard displays the latest skipped checks.
