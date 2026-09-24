"""Email provider protocol and transport result model."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pycrmkit.communication.email.messages import EmailMessage
from pycrmkit.core.json import freeze_json_mapping
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError


class EmailDeliveryStatus(StrEnum):
    """Immediate provider transport result, not downstream mailbox delivery."""

    ACCEPTED = "accepted"
    FAILED = "failed"


def _normalize_optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"communication.email.provider.{field_name}.too_long",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class EmailProviderResult(ValueObject):
    """Normalized result returned by any email provider adapter."""

    provider: str
    status: EmailDeliveryStatus
    provider_message_id: str | None = None
    provider_metadata: Mapping[str, object] = field(default_factory=dict)
    failure_code: str | None = None

    def __post_init__(self) -> None:
        provider = " ".join(unicodedata.normalize("NFKC", self.provider).strip().split())
        if not provider:
            raise ValidationError(
                "email provider name is required",
                code="communication.email.provider.name.required",
            )
        if len(provider) > 120:
            raise ValidationError(
                "email provider name must be at most 120 characters",
                code="communication.email.provider.name.too_long",
            )
        status = EmailDeliveryStatus(self.status)
        provider_message_id = _normalize_optional_text(
            self.provider_message_id,
            field_name="message_id",
            max_length=500,
        )
        failure_code = _normalize_optional_text(
            self.failure_code,
            field_name="failure_code",
            max_length=255,
        )
        if status is EmailDeliveryStatus.ACCEPTED and failure_code is not None:
            raise ValidationError(
                "accepted provider results cannot carry a failure code",
                code="communication.email.provider.result.accepted_failure_conflict",
            )
        if status is EmailDeliveryStatus.FAILED and provider_message_id is not None:
            raise ValidationError(
                "failed provider results cannot carry a provider_message_id",
                code="communication.email.provider.result.failed_message_id_conflict",
            )
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "provider_message_id", provider_message_id)
        object.__setattr__(self, "failure_code", failure_code)
        object.__setattr__(
            self,
            "provider_metadata",
            freeze_json_mapping(self.provider_metadata),
        )


@runtime_checkable
class EmailProvider(Protocol):
    """Transport adapter contract implemented by SMTP, Resend, and future providers."""

    def send(self, message: EmailMessage) -> EmailProviderResult:
        """Submit one immutable email message and return a normalized transport result."""
