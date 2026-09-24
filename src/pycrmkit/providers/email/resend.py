"""Resend implementation of the EmailProvider protocol."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.utils import formataddr
from threading import Lock
from typing import cast

try:
    import resend
    from resend.exceptions import ResendError
except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "The Resend email provider requires the optional dependency: "
        'pip install "pycrmkit[resend]"'
    ) from exc

from pycrmkit.communication.email.messages import EmailMessage
from pycrmkit.communication.email.provider import (
    EmailDeliveryStatus,
    EmailProvider,
    EmailProviderResult,
)
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_RESEND_SDK_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class ResendConfig(ValueObject):
    """Configuration for the official Resend Python SDK adapter."""

    api_key: str = field(repr=False)
    provider_name: str = "resend"

    def __post_init__(self) -> None:
        api_key = unicodedata.normalize("NFKC", self.api_key).strip()
        if not api_key:
            raise ValidationError(
                "Resend API key is required",
                code="communication.email.resend.api_key.required",
            )
        if len(api_key) > 1000:
            raise ValidationError(
                "Resend API key must be at most 1000 characters",
                code="communication.email.resend.api_key.too_long",
            )
        provider_name = " ".join(
            unicodedata.normalize("NFKC", self.provider_name).strip().split()
        )
        if not provider_name:
            raise ValidationError(
                "Resend provider_name is required",
                code="communication.email.resend.provider_name.required",
            )
        if len(provider_name) > 120:
            raise ValidationError(
                "Resend provider_name must be at most 120 characters",
                code="communication.email.resend.provider_name.too_long",
            )
        object.__setattr__(self, "api_key", api_key)
        object.__setattr__(self, "provider_name", provider_name)


@dataclass(slots=True)
class ResendEmailProvider(EmailProvider):
    """EmailProvider backed by the official Resend Python SDK."""

    config: ResendConfig

    def send(self, message: EmailMessage) -> EmailProviderResult:
        """Submit one provider-neutral message through Resend."""

        params = self.build_params(message)
        options = self.build_options(message)
        try:
            response = self._sdk_send(params, options)
        except ResendError as exc:
            return self._failed_from_resend_error(exc)
        except ValueError as exc:
            return EmailProviderResult(
                provider=self.config.provider_name,
                status=EmailDeliveryStatus.FAILED,
                failure_code="resend.invalid_request",
                provider_metadata={
                    "transport": "resend",
                    "error_type": type(exc).__name__,
                },
            )

        provider_message_id = response.get("id")
        if not isinstance(provider_message_id, str) or not provider_message_id.strip():
            return EmailProviderResult(
                provider=self.config.provider_name,
                status=EmailDeliveryStatus.FAILED,
                failure_code="resend.invalid_response",
                provider_metadata={
                    "transport": "resend",
                    "response_keys": sorted(str(key) for key in response),
                },
            )

        metadata: dict[str, object] = {"transport": "resend"}
        headers = response.get("http_headers")
        if isinstance(headers, Mapping):
            self._copy_response_metadata(headers, metadata)

        return EmailProviderResult(
            provider=self.config.provider_name,
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=provider_message_id,
            provider_metadata=metadata,
        )

    def build_params(self, message: EmailMessage) -> resend.Emails.SendParams:
        """Map EmailMessage into the Resend Send Email request shape."""

        params: resend.Emails.SendParams = {
            "from": message.sender.value,
            "to": [
                formataddr((recipient.display_name or "", recipient.address.value))
                for recipient in message.recipients
            ],
            "headers": {
                "X-PyCRMKit-Intent-ID": str(message.intent_id),
            },
        }
        if message.content.subject is not None:
            params["subject"] = message.content.subject
        if message.content.text_body is not None:
            params["text"] = message.content.text_body
        if message.content.html_body is not None:
            params["html"] = message.content.html_body
        return params

    @staticmethod
    def build_options(message: EmailMessage) -> resend.Emails.SendOptions | None:
        """Map provider-independent idempotency onto Resend send options."""

        if message.idempotency_key is None:
            return None
        return {"idempotency_key": message.idempotency_key}

    def _sdk_send(
        self,
        params: resend.Emails.SendParams,
        options: resend.Emails.SendOptions | None,
    ) -> Mapping[str, object]:
        # Resend's sync SDK uses module-level api_key configuration. Serialize the
        # set/send/restore sequence so multiple provider instances cannot leak keys.
        with _RESEND_SDK_LOCK:
            previous_api_key = resend.api_key
            resend.api_key = self.config.api_key
            try:
                response = resend.Emails.send(params, options)
            finally:
                resend.api_key = previous_api_key
        return cast(Mapping[str, object], response)

    def _failed_from_resend_error(self, exc: ResendError) -> EmailProviderResult:
        error_type = str(getattr(exc, "error_type", type(exc).__name__))
        metadata: dict[str, object] = {
            "transport": "resend",
            "error_type": error_type,
        }
        code = getattr(exc, "code", None)
        if isinstance(code, (str, int)):
            metadata["status_code"] = code
        headers = getattr(exc, "headers", None)
        if isinstance(headers, Mapping):
            self._copy_response_metadata(headers, metadata)

        return EmailProviderResult(
            provider=self.config.provider_name,
            status=EmailDeliveryStatus.FAILED,
            failure_code=f"resend.{self._error_token(error_type)}",
            provider_metadata=metadata,
        )

    @staticmethod
    def _copy_response_metadata(
        headers: Mapping[object, object],
        metadata: dict[str, object],
    ) -> None:
        normalized = {str(key).casefold(): str(value) for key, value in headers.items()}
        for source, target in (
            ("x-request-id", "request_id"),
            ("x-resend-request-id", "request_id"),
            ("ratelimit-limit", "rate_limit"),
            ("ratelimit-remaining", "rate_limit_remaining"),
            ("ratelimit-reset", "rate_limit_reset"),
        ):
            if source in normalized and target not in metadata:
                metadata[target] = normalized[source]

    @staticmethod
    def _error_token(value: str) -> str:
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", value)
        token = re.sub(r"[^a-z0-9_]+", "_", snake.casefold()).strip("_")
        return token or "error"


__all__ = ["ResendConfig", "ResendEmailProvider"]
