"""Validated configuration for django-tron-payments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class PaymentAsset:
    """An asset accepted into and swept from managed wallets."""

    code: str
    kind: str
    decimals: int
    minimum_deposit_atomic: int
    contract_address: str = ""


@dataclass(frozen=True)
class TronPaymentsSettings:
    """Resolved application settings with safe operational defaults."""

    network: str
    trongrid_api_key: str
    treasury_address: str
    encryption_backend: str
    encryption_options: dict[str, Any]
    assets: tuple[PaymentAsset, ...]
    request_timeout_seconds: int
    poll_page_size: int
    trx_sweep_reserve_sun: int
    trc20_fee_limit_sun: int
    task_retry_limit: int

    def asset(self, code: str) -> PaymentAsset:
        normalized_code = code.upper()
        for asset in self.assets:
            if asset.code == normalized_code:
                return asset
        raise ImproperlyConfigured(
            f"TRON_PAYMENTS does not configure the {normalized_code!r} asset."
        )


def get_tron_settings() -> TronPaymentsSettings:
    """Return the current, validated settings without caching secrets."""
    raw_settings = getattr(settings, "TRON_PAYMENTS", {})
    if not isinstance(raw_settings, dict):
        raise ImproperlyConfigured("TRON_PAYMENTS must be a dictionary.")

    network = str(raw_settings.get("NETWORK", "nile")).lower()
    if network not in {"mainnet", "nile", "shasta"}:
        raise ImproperlyConfigured("TRON_PAYMENTS['NETWORK'] must be mainnet, nile, or shasta.")
    assets = _parse_assets(raw_settings.get("ASSETS", []))
    encryption_options = raw_settings.get("ENCRYPTION_OPTIONS", {})
    if not isinstance(encryption_options, dict):
        raise ImproperlyConfigured("TRON_PAYMENTS['ENCRYPTION_OPTIONS'] must be a dictionary.")

    return TronPaymentsSettings(
        network=network,
        trongrid_api_key=_required_string(raw_settings, "TRONGRID_API_KEY"),
        treasury_address=_required_string(raw_settings, "TREASURY_ADDRESS"),
        encryption_backend=str(
            raw_settings.get(
                "ENCRYPTION_BACKEND",
                "django_tron_payments.crypto.fernet.FernetKeyCipher",
            )
        ),
        encryption_options=encryption_options,
        assets=assets,
        request_timeout_seconds=_positive_int(raw_settings, "REQUEST_TIMEOUT_SECONDS", 15),
        poll_page_size=_positive_int(raw_settings, "POLL_PAGE_SIZE", 100),
        trx_sweep_reserve_sun=_nonnegative_int(
            raw_settings, "TRX_SWEEP_RESERVE_SUN", 1_000_000
        ),
        trc20_fee_limit_sun=_positive_int(raw_settings, "TRC20_FEE_LIMIT_SUN", 3_000_000),
        task_retry_limit=_nonnegative_int(raw_settings, "TASK_RETRY_LIMIT", 5),
    )


def _parse_assets(raw_assets: Any) -> tuple[PaymentAsset, ...]:
    if not isinstance(raw_assets, list):
        raise ImproperlyConfigured("TRON_PAYMENTS['ASSETS'] must be a list.")

    parsed_assets = [
        PaymentAsset(code="TRX", kind="TRX", decimals=6, minimum_deposit_atomic=1)
    ]
    seen_codes = {"TRX"}
    seen_contracts: set[str] = set()

    for item in raw_assets:
        if not isinstance(item, dict):
            raise ImproperlyConfigured("Every TRON_PAYMENTS asset must be a dictionary.")
        code = str(item.get("CODE", "")).upper().strip()
        kind = str(item.get("KIND", "TRC20")).upper()
        contract_address = str(item.get("CONTRACT_ADDRESS", "")).strip()
        decimals = item.get("DECIMALS")
        minimum = item.get("MINIMUM_DEPOSIT_ATOMIC", 1)

        if not code or code == "TRX" or code in seen_codes:
            raise ImproperlyConfigured("Asset codes must be unique non-TRX identifiers.")
        if kind != "TRC20" or not contract_address:
            raise ImproperlyConfigured("Configured assets must be TRC20 assets with a contract address.")
        if not isinstance(decimals, int) or not 0 <= decimals <= 255:
            raise ImproperlyConfigured(f"Asset {code!r} needs DECIMALS between 0 and 255.")
        if not isinstance(minimum, int) or minimum < 1:
            raise ImproperlyConfigured(
                f"Asset {code!r} needs a positive MINIMUM_DEPOSIT_ATOMIC."
            )
        if contract_address in seen_contracts:
            raise ImproperlyConfigured("TRC20 contract addresses must be unique.")

        parsed_assets.append(
            PaymentAsset(code, kind, decimals, minimum, contract_address)
        )
        seen_codes.add(code)
        seen_contracts.add(contract_address)

    return tuple(parsed_assets)


def _required_string(raw_settings: dict[str, Any], name: str) -> str:
    value = raw_settings.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ImproperlyConfigured(f"TRON_PAYMENTS['{name}'] must be a non-empty string.")
    return value.strip()


def _positive_int(raw_settings: dict[str, Any], name: str, default: int) -> int:
    value = raw_settings.get(name, default)
    if not isinstance(value, int) or value < 1:
        raise ImproperlyConfigured(f"TRON_PAYMENTS['{name}'] must be a positive integer.")
    return value


def _nonnegative_int(raw_settings: dict[str, Any], name: str, default: int) -> int:
    value = raw_settings.get(name, default)
    if not isinstance(value, int) or value < 0:
        raise ImproperlyConfigured(f"TRON_PAYMENTS['{name}'] must be a non-negative integer.")
    return value
