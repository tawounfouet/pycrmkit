"""Unit tests for the standard-library SMTP adapter."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationIntentId,
    CommunicationRecipient,
    EmailDeliveryStatus,
    EmailMessage,
)
from pycrmkit.exceptions import ValidationError
from pycrmkit.providers.email import SMTPConfig, SMTPEmailProvider, SMTPSecurity
from pycrmkit.providers.email import smtp as smtp_module

BASE = datetime(2026, 9, 24, 21, 0, tzinfo=UTC)


def _message() -> EmailMessage:
    del BASE
    return EmailMessage(
        intent_id=CommunicationIntentId(
            UUID("00000000-0000-0000-0000-000000000501")
        ),
        sender=CommunicationAddress(CommunicationChannel.EMAIL, "sales@example.com"),
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
        idempotency_key="mail-501",
    )


class FakeSMTP:
    instances: list[FakeSMTP] = []
    refused: dict[str, tuple[int, bytes]] = {}

    def __init__(
        self,
        host: str,
        port: int,
        *,
        local_hostname: str | None = None,
        timeout: float,
    ) -> None:
        self.host = host
        self.port = port
        self.local_hostname = local_hostname
        self.timeout = timeout
        self.calls: list[str] = []
        self.sent = None
        type(self).instances.append(self)

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self, *, context: object) -> None:
        assert context is not None
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        assert username == "user"
        assert password == "secret"
        self.calls.append("login")

    def send_message(self, message: object) -> dict[str, tuple[int, bytes]]:
        self.sent = message
        self.calls.append("send_message")
        return dict(type(self).refused)


class AuthFailingSMTP(FakeSMTP):
    def login(self, username: str, password: str) -> None:
        del username, password
        raise smtplib.SMTPAuthenticationError(535, b"authentication failed")


@pytest.fixture(autouse=True)
def _reset_fakes() -> None:
    FakeSMTP.instances.clear()
    FakeSMTP.refused = {}


def test_build_message_maps_headers_and_multipart_content() -> None:
    provider = SMTPEmailProvider(SMTPConfig(host="smtp.example.com"))

    mime = provider.build_message(_message())

    assert mime["From"] == "sales@example.com"
    assert mime["To"] == "Buyer <buyer@example.com>, other@example.com"
    assert mime["Subject"] == "Proposal"
    assert mime["X-PyCRMKit-Idempotency-Key"] == "mail-501"
    assert mime["X-PyCRMKit-Intent-ID"] == "00000000-0000-0000-0000-000000000501"
    assert mime["Message-ID"]
    assert mime.is_multipart()


def test_starttls_send_maps_partial_refusal_to_accepted_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSMTP.refused = {"other@example.com": (550, b"rejected")}
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", FakeSMTP)
    provider = SMTPEmailProvider(
        SMTPConfig(
            host="smtp.example.com",
            username="user",
            password="secret",
        )
    )

    result = provider.send(_message())

    assert result.status is EmailDeliveryStatus.ACCEPTED
    assert result.provider_message_id is not None
    assert result.provider_metadata["accepted_recipient_count"] == 1
    assert result.provider_metadata["refused_recipient_count"] == 1
    client = FakeSMTP.instances[0]
    assert client.calls == ["ehlo", "starttls", "ehlo", "login", "send_message"]


def test_authentication_failure_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", AuthFailingSMTP)
    provider = SMTPEmailProvider(
        SMTPConfig(
            host="smtp.example.com",
            username="user",
            password="secret",
        )
    )

    result = provider.send(_message())

    assert result.status is EmailDeliveryStatus.FAILED
    assert result.failure_code == "smtp.authentication_failed"
    assert result.provider_metadata["smtp_code"] == 535


def test_smtp_config_rejects_incomplete_credentials() -> None:
    with pytest.raises(ValidationError) as error:
        SMTPConfig(host="smtp.example.com", username="user")

    assert error.value.code == "communication.email.smtp.credentials.incomplete"


def test_smtp_config_accepts_explicit_tls_mode() -> None:
    config = SMTPConfig(
        host="smtp.example.com",
        port=465,
        security=SMTPSecurity.TLS,
    )

    assert config.security is SMTPSecurity.TLS
    assert "password" not in repr(config)
