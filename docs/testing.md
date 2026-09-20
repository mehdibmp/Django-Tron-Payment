# Testing Guide

The package test suite never connects to TronGrid or broadcasts a transaction. Network client behavior is mocked at the service boundary.

## Run the suite

```bash
python -m pip install -e '.[test]'
pytest
```

## Quality checks

```bash
ruff check src tests
ruff format --check src tests
python -m compileall -q src tests
python -m django check --settings=tests.settings
```

## Test focus

The suite covers:

- Fernet encryption/decryption and invalid-key rejection.
- One wallet per user/network and public-address-only access.
- Idempotent recording of confirmed inbound transfers.
- Asset minimum handling without live network requests.
- Sweep state transitions, persisted transaction IDs, and receipt confirmation.
- Staff-only dashboard access and POST-only operations dispatch.

Before a production deployment, run an end-to-end Nile test with a separately funded test wallet, a verified testnet token contract, real Celery workers, and a non-production treasury address.
