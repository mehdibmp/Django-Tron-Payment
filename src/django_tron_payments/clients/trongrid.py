"""TronGrid-backed client for confirmed transfer discovery and broadcast receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests
from django.core.exceptions import ValidationError
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import is_base58check_address

from django_tron_payments.clients.base import ObservedTransfer, TronClientError
from django_tron_payments.conf import PaymentAsset, TronPaymentsSettings

_ENDPOINTS = {
    "mainnet": "https://api.trongrid.io",
    "nile": "https://nile.trongrid.io",
    "shasta": "https://api.shasta.trongrid.io",
}


class TronGridClient:
    """Uses TronGrid so deployments do not require a self-hosted TRON node."""

    def __init__(self, configured: TronPaymentsSettings) -> None:
        self.configured = configured
        self.endpoint = _ENDPOINTS[configured.network]
        self.headers = {"TRON-PRO-API-KEY": configured.trongrid_api_key}
        self.sdk = Tron(
            HTTPProvider(
                endpoint_uri=f"{self.endpoint}/",
                api_key=configured.trongrid_api_key,
            )
        )

    @staticmethod
    def validate_address(address: str) -> str:
        """Reject malformed recipient, sender, contract, and treasury addresses."""
        if not is_base58check_address(address):
            raise ValidationError("A valid base58check TRON address is required.")
        return address

    def confirmed_transfers(
        self, address: str, asset: PaymentAsset
    ) -> list[ObservedTransfer]:
        """Return recent confirmed inbound transfers for a single managed wallet."""
        self.validate_address(address)
        if asset.kind == "TRX":
            payload = self._get(f"/v1/accounts/{address}/transactions", {"only_to": "true"})
            return self._parse_trx_transfers(address, payload)
        payload = self._get(
            f"/v1/accounts/{address}/transactions/trc20",
            {
                "only_to": "true",
                "contract_address": asset.contract_address,
            },
        )
        return self._parse_trc20_transfers(address, asset, payload)

    def transaction_confirmed(self, transaction_id: str, isTRX=False) -> bool:
        """Check a SolidityNode-backed transaction receipt before finalizing state."""
        response = self._post(
            "/walletsolidity/gettransactionbyid", {"value": transaction_id}
        )
        print(response)
        return bool(response.get("id")) and response.get("receipt", {}).get("result") == "SUCCESS"

    def get_trx_balance_sun(self, address: str) -> int:
        """Return native TRX balance in SUN, without using float conversions."""
        self.validate_address(address)
        return int(self.sdk.get_account_balance(address) * 1_000_000)

    def get_trc20_balance(self, address: str, asset: PaymentAsset) -> int:
        """Return the configured token balance in its smallest integer unit."""
        self.validate_address(address)
        contract = self.sdk.get_contract(asset.contract_address)
        return int(contract.functions.balanceOf(address))

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self.endpoint}{path}",
                headers=self.headers,
                params={**params, "only_confirmed": "true", "limit": self.configured.poll_page_size},
                timeout=self.configured.request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise TronClientError("TronGrid confirmed-transfer query failed.") from exc

    def _post(self, path: str, payload: dict[str, str]) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.endpoint}{path}",
                headers=self.headers,
                json=payload,
                timeout=self.configured.request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise TronClientError("TronGrid transaction-receipt query failed.") from exc

    def _parse_trx_transfers(
        self, address: str, payload: dict[str, Any]
    ) -> list[ObservedTransfer]:
        transfers: list[ObservedTransfer] = []
        for row in payload.get("data", []):
            contract = row.get("raw_data", {}).get("contract", [{}])[0]
            parameter = contract.get("parameter", {}).get("value", {})
            if contract.get("type") != "TransferContract" or parameter.get("to_address") != self._hex_address(address):
                continue
            amount = int(parameter.get("amount", 0))
            if amount <= 0:
                continue
            transfers.append(
                ObservedTransfer(
                    transaction_id=row["txID"],
                    event_index=0,
                    sender_address=self._base58_address(parameter["owner_address"]),
                    recipient_address=address,
                    amount_atomic=amount,
                    observed_at=self._timestamp(row.get("block_timestamp")),
                    raw_payload=row,
                )
            )
        return transfers

    def _parse_trc20_transfers(
        self, address: str, asset: PaymentAsset, payload: dict[str, Any]
    ) -> list[ObservedTransfer]:
        transfers: list[ObservedTransfer] = []
        for index, row in enumerate(payload.get("data", [])):
            if row.get("to") != address or row.get("token_info", {}).get("address") != asset.contract_address:
                continue
            amount = int(row.get("value", 0))
            if amount <= 0:
                continue
            transfers.append(
                ObservedTransfer(
                    transaction_id=row["transaction_id"],
                    event_index=index,
                    sender_address=row["from"],
                    recipient_address=address,
                    amount_atomic=amount,
                    observed_at=self._timestamp(row.get("block_timestamp")),
                    raw_payload=row,
                )
            )
        return transfers

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        return datetime.fromtimestamp(int(value or 0) / 1000, tz=UTC)

    def _hex_address(self, address: str) -> str:
        return self.sdk.to_hex_address(address).lower()

    def _base58_address(self, address: str) -> str:
        return self.sdk.to_base58check_address(address)
