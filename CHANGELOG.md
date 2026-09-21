# Changelog

All notable changes to this project are documented in this file.

## 0.1.0 — 2026-09-19

### Added

- Reusable Django application packaging.
- Encrypted custodial wallets for Django users.
- TronGrid-powered confirmed deposit monitoring for TRX and configured TRC-20 assets.
- Celery tasks for monitoring, sweeping, and confirmed-receipt processing.
- Django administration dashboard and operational management commands.
- Fernet/MultiFernet encryption backend and extension point for KMS/HSM-backed key protection.
### Changed

- TRC-20 sweep planning now checks the source wallet's TRX balance before reading the token balance or creating a sweep. Wallets below `TRC20_FEE_LIMIT_SUN` are not queued; the reason and current/required SUN values are recorded in an idempotent `sweep.skipped` audit event.
- Native TRX sweeps preserve the larger of `TRX_SWEEP_RESERVE_SUN` and `TRC20_FEE_LIMIT_SUN` whenever TRC-20 assets are configured, preventing fee funds from being swept away.
- The staff operations dashboard displays skipped token sweeps and their fee-readiness details.

### Documentation

- Added a step-by-step usage guide covering wallet addresses, balances, confirmed payments, confirmed sweeps, operations-console mounting, and fee-readiness troubleshooting.
- Expanded installation, configuration, Celery, operations, security, and manual-command documentation.