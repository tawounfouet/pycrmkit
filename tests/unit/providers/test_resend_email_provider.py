"""Unit tests for the Resend email adapter."""

from __future__ import annotations

from uuid import UUID

import pytest
from resend.exceptions import ResendError

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationIntentId,
    CommunicationRecipient,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProvider,
)
from pycrmkit.exceptions import ValidationError
from pycrmkit.providers.email import resend as resend_module
from pycrmkit.providers.email.resend import ResendConfig, ResendEmailProvider


def _message() -> EmailMessage:
    return EmailMessage(
        intent_id=CommunicationIntentId(
            UUID("00000000-0000-0000-0000-000000000601")
        ),
        sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
        recipients=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "buyer@example.com",
                ),
                display_name="Buyer",
            ),
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "other@example.com",
                )
            ),
        ),
        content=CommunicationContent(
            subject="Proposal",
            text_body="Plain body",
            html_body="<strong>HTML body</strong>",
        ),
        idempotency_key="mail-601",
    )


def test_resend_provider_satisfies_email_provider_protocol() -> None:
    provider = ResendEmailProvider(ResendConfig(api_key="re_test"))

    assert isinstance(provider, EmailProvider)


def test_build_params_and_options_map_provider_neutral_message() -> None:
    provider = ResendEmailProvider(ResendConfig(api_key="re_test"))

    params = provider.build_params(_message())
    options = provider.build_options(_message())

    assert params == {
        "from": "sales@example.com",
        "to": ["Buyer <buyer@example.com>", "other@example.com"],
        "headers": {
            "X-PyCRMKit-Intent-ID": "00000000-0000-0000-0000-000000000601",
        },
        "subject": "Proposal",
        "text": "Plain body",
        "html": "<strong>HTML body</strong>",
    }
    assert options == {"idempotency_key": "mail-601"}


def test_send_maps_provider_message_id_and_response_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    resend_module.resend.api_key = "re_original"

    def fake_send(
        params: dict[str, object],
        options: dict[str, str] | None,
    ) -> dict[str, object]:
        captured["params"] = params
        captured["options"] = options
        captured["api_key"] = resend_module.resend.api_key
        return {
            "id": "resend-message-601",
            "http_headers": {
                "x-request-id": "req-601",
                "ratelimit-remaining": "99",
            },
        }

    monkeypatch.setattr(resend_module.resend.Emails, "send", fake_send)
    provider = ResendEmailProvider(
        ResendConfig(api_key="re_secret", provider_name="resend-primary")
    )

    result = provider.send(_message())

    assert result.status is EmailDeliveryStatus.ACCEPTED
    assert result.provider == "resend-primary"
    assert result.provider_message_id == "resend-message-601"
    assert result.provider_metadata["transport"] == "resend"
    assert result.provider_metadata["request_id"] == "req-601"
    assert result.provider_metadata["rate_limit_remaining"] == "99"
    assert captured["api_key"] == "re_secret"
    assert captured["options"] == {"idempotency_key": "mail-601"}
    assert resend_module.resend.api_key == "re_original"


def test_resend_error_is_normalized_without_exposing_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_send(
        params: dict[str, object],
        options: dict[str, str] | None,
    ) -> dict[str, object]:
        del params, options
        raise ResendError(
            code=429,
            error_type="rate_limit_exceeded",
            message="sensitive provider text",
            suggested_action="retry later",
            headers={"x-request-id": "req-rate-limit"},
        )

    monkeypatch.setattr(resend_module.resend.Emails, "send", fake_send)
    provider = ResendEmailProvider(ResendConfig(api_key="re_secret"))

    result = provider.send(_message())

    assert result.status is EmailDeliveryStatus.FAILED
    assert result.failure_code == "resend.rate_limit_exceeded"
    assert result.provider_message_id is None
    assert result.provider_metadata == {
        "transport": "resend",
        "error_type": "rate_limit_exceeded",
        "status_code": 429,
        "request_id": "req-rate-limit",
    }
    assert "sensitive provider text" not in repr(result.provider_metadata)


def test_client_side_value_error_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_send(
        params: dict[str, object],
        options: dict[str, str] | None,
    ) -> dict[str, object]:
        del params, options
        raise ValueError("invalid SDK request")

    monkeypatch.setattr(resend_module.resend.Emails, "send", fake_send)
    provider = ResendEmailProvider(ResendConfig(api_key="re_secret"))

    result = provider.send(_message())

    assert result.status is EmailDeliveryStatus.FAILED
    assert result.failure_code == "resend.invalid_request"
    assert result.provider_metadata["error_type"] == "ValueError"


def test_missing_provider_message_id_is_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_send(
        params: dict[str, object],
        options: dict[str, str] | None,
    ) -> dict[str, object]:
        del params, options
        return {"http_headers": {"x-request-id": "req-no-id"}}

    monkeypatch.setattr(resend_module.resend.Emails, "send", fake_send)
    provider = ResendEmailProvider(ResendConfig(api_key="re_secret"))

    result = provider.send(_message())

    assert result.status is EmailDeliveryStatus.FAILED
    assert result.failure_code == "resend.invalid_response"
    assert result.provider_message_id is None


def test_resend_config_requires_api_key_and_hides_secret() -> None:
    with pytest.raises(ValidationError) as error:
        ResendConfig(api_key=" ")

    assert error.value.code == "communication.email.resend.api_key.required"

    config = ResendConfig(api_key="re_super_secret")
    assert "re_super_secret" not in repr(config)
