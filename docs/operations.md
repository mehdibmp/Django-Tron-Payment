# Operations Runbook

## Required workers

Run a Celery worker and Celery Beat process for the host Django project. Configure Beat with the four package tasks shown in [configuration.md](configuration.md):

1. Reconcile confirmed deposits frequently.
2. Queue candidate sweeps five times per day.
3. Broadcast newly queued sweeps shortly afterward.
4. Confirm outbound receipts frequently.

Use a single Beat scheduler instance. Multiple schedulers can enqueue duplicate work even though the database-level state handling limits duplicate effects.

## Daily checks

Review **TRON payment operations** in Django admin:

- Confirm the active network and treasury address are expected.
- Review failed and stale outbound sweeps.
- Confirm queue/broadcast/receipt task activity is current.
- Investigate any deposit or sweep entries whose asset, amount, or destination is unexpected.
- Verify the configured treasury balance independently in a trusted explorer or custody system.

## Sweep states

| State | Meaning | Operator action |
| --- | --- | --- |
| `queued` | A wallet balance was eligible for collection. | Ensure the scheduled broadcast task is healthy. |
| `building` | A transaction ID was signed and persisted; the result may be ambiguous. | Do not create another sweep. Run receipt confirmation and investigate the known transaction ID. |
| `broadcast` | The provider accepted the signed transaction. | Wait for confirmed receipt processing. |
| `confirmed` | A confirmed successful network receipt was observed. | No action needed. |
| `failed` | Signing or pre-broadcast preparation failed without a persisted transaction ID. | Correct the underlying issue, verify source funds, then use a controlled retry procedure. |

## TRX fee readiness and skipped token sweeps

During the queue stage, every configured TRC-20 asset is checked against the source wallet's current TRX balance. The package compares that balance in SUN with `TRC20_FEE_LIMIT_SUN` before reading the token balance or creating a `TreasurySweep` record.

When the wallet does not have enough TRX for the configured fee limit:

- the token sweep is not placed in the queue;
- no token transfer is signed or broadcast;
- one idempotent `sweep.skipped` audit event is recorded for the current wallet, asset, balance, and threshold;
- the event metadata includes `reason=insufficient_trx_for_fee`, `trx_balance_sun`, and `required_trx_sun`;
- the operations dashboard and Payment audit events admin page show the reason and values.

The native TRX sweep is evaluated separately and still respects `TRX_SWEEP_RESERVE_SUN`. After deliberately funding the wallet, run the queue stage again. A token sweep can then be created only if its token balance also meets `MINIMUM_DEPOSIT_ATOMIC`.

## Ambiguous broadcast recovery

A worker or network timeout after a signed transaction can leave a sweep in `building`. This is deliberate: the package retains the locally determined transaction ID and will not automatically sign a replacement transaction.

1. Open the sweep in admin and copy the transaction ID.
2. Inspect its confirmed state through your trusted TRON explorer/API.
3. Run `python manage.py sweep_tron confirm` or queue receipt confirmation from the operations console.
4. If the transaction is confirmed, allow the receipt task to mark it `confirmed`.
5. If it is definitively absent after the network expiration window, document the evidence, have a second operator review it, and only then create an explicit recovery process under your organization’s custody policy.

## Manual commands

```bash
python manage.py reconcile_tron
python manage.py sweep_tron queue
python manage.py sweep_tron broadcast
python manage.py sweep_tron confirm
# Or run all three sweep stages sequentially:
python manage.py sweep_tron all
```

Manual commands are operational fallbacks, not a replacement for Celery Beat. Run them from a controlled deployment environment and verify the active network before starting a transfer lifecycle.

## Incident response

If you suspect a credential or key-custody compromise:

1. Disable workers and Beat before further transfers are created.
2. Restrict access to the deployment and secret manager.
3. Preserve logs, database state, task records, and transaction IDs for investigation.
4. Rotate the TronGrid API key and encryption keys according to your key-management procedure.
5. Assess each managed-wallet balance and immediately move funds only through an approved incident process.
6. Resume services only after independent reconciliation and review.
