"""Webhook stdlib transport policy tests."""

import pytest

from pycrmkit.webhooks import (
    StdlibWebhookTransport,
    WebhookRequest,
    WebhookTransportError,
)


def test_default_transport_blocks_loopback_destination_before_request() -> None:
    transport = StdlibWebhookTransport()
    request = WebhookRequest(
        url="http://127.0.0.1:9999/hook",
        body=b"{}",
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(WebhookTransportError) as error:
        transport.send(request)

    assert error.value.code == "webhook.transport.destination_forbidden"
