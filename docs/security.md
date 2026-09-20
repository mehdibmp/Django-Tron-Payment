# Security and Custody Guide

## Custody model

This package is custodial: it generates a private key for every managed wallet and signs treasury sweeps on the operator's infrastructure. It must be treated as payment infrastructure, not as a general-purpose wallet UI.

Private keys are never returned by the package's public service API, included in audit events, rendered in Django admin, or sent to TronGrid. The encrypted key column is excluded from the Django admin form entirely.

## Encryption backends

The default `FernetKeyCipher` reads `TRON_PAYMENTS["ENCRYPTION_OPTIONS"]["KEYS"]`, a list of Fernet-compatible keys. The first key encrypts new wallets; all listed keys may decrypt historical wallets. Rotate by adding a new key first, then re-encrypting records through a controlled migration or custom operational procedure, and only then remove the retired key.

For production funds, point `ENCRYPTION_BACKEND` at an operator-provided KMS/HSM-backed class. It must provide `encrypt(plaintext: str) -> str` and `decrypt(token: str) -> str`. Keep KMS identity permissions restricted to the web and worker service identities that require custody access.

## Required controls

- Keep `TRONGRID_API_KEY`, encryption keys, and KMS credentials out of repository files, logs, error trackers, and Django settings committed to source control.
- Use a distinct TronGrid key and secret-encryption key set per environment.
- Restrict Django admin access with MFA and least-privilege staff permissions.
- Run Celery workers with a distinct, minimal service identity.
- Use HTTPS for all application and admin traffic.
- Back up the database and encryption-key recovery material through separately controlled processes.
- Monitor failed sweeps, queued sweeps that do not settle, API quota errors, and unusual wallet growth.
- Test all releases and operational recovery flows on Nile before Mainnet.

## Treasury changes

Changing the configured treasury address changes where future sweeps are sent. Require change review, independently validate the address, deploy the change through controlled configuration management, and test it on Nile first.

## TRC-20 gas

TRC-20 transfers consume TRX bandwidth/energy. A token-only deposit cannot be swept unless its managed wallet also has sufficient TRX. This package deliberately does not auto-fund wallets: uncontrolled gas funding can create loss and abuse paths. Design, approve, and monitor any gas-sponsorship service separately.

## Incident response

1. Stop Celery Beat and workers that can queue or broadcast sweeps.
2. Preserve logs, database records, task IDs, and relevant transaction IDs without exporting secrets.
3. Check `building` and `broadcast` sweeps against confirmed network receipts before taking any manual action.
4. Do not rebroadcast an ambiguous signed transaction automatically.
5. Rotate API credentials and encryption access where compromise is possible.
6. Resume only after reconciliation and treasury-balance review are complete.
