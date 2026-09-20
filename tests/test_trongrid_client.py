from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ValidationError

from django_tron_payments.clients.trongrid import TronGridClient
from django_tron_payments.conf import PaymentAsset, get_tron_settings


def test_client_rejects_an_invalid_tron_address():
    with pytest.raises(ValidationError):
        TronGridClient.validate_address("not-a-tron-address")


def test_client_queries_only_confirmed_trx_transfers(settings):
    response = Mock()
    response.json.return_value = {"data": []}
    response.raise_for_status.return_value = None
    client = TronGridClient(get_tron_settings())

    with patch("django_tron_payments.clients.trongrid.requests.get", return_value=response) as get:
        transfers = client.confirmed_transfers(
            "TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
            PaymentAsset("TRX", "TRX", 6, 1),
        )

    assert transfers == []
    assert get.call_args.kwargs["params"]["only_confirmed"] is True
    assert get.call_args.kwargs["params"]["only_to"] == "true"


def test_client_parses_a_confirmed_trc20_transfer_without_network_access(settings):
    client = TronGridClient(get_tron_settings())
    asset = PaymentAsset("USDT", "TRC20", 6, 1, "TR7NHqjeKQxGTCi8q8ZY4pL8otS6M8D9T")
    payload = {
        "data": [
            {
                "transaction_id": "a" * 64,
                "from": "TQxYyZ1x4ZsVjWQdR4oKdu9wZE7KAjrfpD",
                "to": "TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
                "value": "1000000",
                "block_timestamp": 1_704_067_200_000,
                "token_info": {"address": asset.contract_address},
            }
        ]
    }

    transfers = client._parse_trc20_transfers(
        "TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
        asset,
        payload,
    )

    assert len(transfers) == 1
    assert transfers[0].amount_atomic == 1_000_000
    assert transfers[0].transaction_id == "a" * 64
