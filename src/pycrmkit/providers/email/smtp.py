"""Standard-library SMTP implementation of the EmailProvider protocol."""

from __future__ import annotations

import smtplib
import ssl
import unicodedata
from dataclasses import dataclass, field
from email.message import EmailMessage as MIMEEmailMessage
from email.utils import formataddr, make_msgid
from enum import StrEnum

from pycrmkit.communication.email.messages import EmailMessage
from pycrmkit.communication.email.provider import (
    EmailDeliveryStatus,
    EmailProvider,
    EmailProviderResult,
)
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError


class SMTPSecurity(StrEnum):
    """Connection security mode for the stdlib SMTP adapter."""

    PLAIN = "plain"
    STARTTLS = "starttls"
    TLS = "tls"


@dataclass(frozen=True, slots=True)
class SMTPConfig(ValueObject):
    """Connection settings for SMTPEmailProvider."""

    host: str
    port: int = 587
    security: SMTPSecurity = SMTPSecurity.STARTTLS
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    timeout: float = 30.0
    local_hostname: str | None = None

    def __post_init__(self) -> None:
        host = " ".join(unicodedata.normalize("NFKC", self.host).strip().split())
        if not host:
            raise ValidationError(
                "SMTP host is required",
                code="communication.email.smtp.host.required",
            )
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValidationError(
                "SMTP port must be between 1 and 65535",
                code="communication.email.smtp.port.invalid",
            )
        security = SMTPSecurity(self.security)
        if self.timeout <= 0:
            raise ValidationError(
                "SMTP timeout must be positive",
                code="communication.email.smtp.timeout.invalid",
            )
        username = self._optional_single_line(self.username)
        password = self.password
        if (username is None) != (password is None):
            raise ValidationError(
                "SMTP username and password must be configured together",
                code="communication.email.smtp.credentials.incomplete",
            )
        local_hostname = self._optional_single_line(self.local_hostname)
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "security", security)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "local_hostname", local_hostname)

    @staticmethod
    def _optional_single_line(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
        return normalized or None


@dataclass(slots=True)
class SMTPEmailProvider(EmailProvider):
    """EmailProvider backed only by Python's smtplib and email packages."""

    config: SMTPConfig
    provider_name: str = "smtp"

    def __post_init__(self) -> None:
        provider_name = " ".join(
            unicodedata.normalize("NFKC", self.provider_name).strip().split()
        )
        if not provider_name:
            raise ValidationError(
                "SMTP provider_name is required",
                code="communication.email.smtp.provider_name.required",
            )
        self.provider_name = provider_name

    def send(self, message: EmailMessage) -> EmailProviderResult:
        """Submit one email and normalize SMTP outcomes into EmailProviderResult."""

        mime_message = self.build_message(message)
        message_id = str(mime_message["Message-ID"])
        recipient_count = len(message.recipients)
        try:
            refused = self._send_message(mime_message)
        except smtplib.SMTPAuthenticationError as exc:
            return self._failed("smtp.authentication_failed", exc)
        except smtplib.SMTPRecipientsRefused as exc:
            return self._failed(
                "smtp.recipients_refused",
                exc,
                refused_recipient_count=len(exc.recipients),
            )
        except smtplib.SMTPSenderRefused as exc:
            return self._failed("smtp.sender_refused", exc)
        except smtplib.SMTPConnectError as exc:
            return self._failed("smtp.connect_error", exc)
        except smtplib.SMTPServerDisconnected as exc:
            return self._failed("smtp.disconnected", exc)
        except TimeoutError as exc:
            return self._failed("smtp.timeout", exc)
        except OSError as exc:
            return self._failed("smtp.network_error", exc)
        except smtplib.SMTPException as exc:
            return self._failed("smtp.error", exc)

        refused_count = len(refused)
        return EmailProviderResult(
            provider=self.provider_name,
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=message_id,
            provider_metadata={
                "security": self.config.security.value,
                "accepted_recipient_count": recipient_count - refused_count,
                "refused_recipient_count": refused_count,
            },
        )

    def build_message(self, message: EmailMessage) -> MIMEEmailMessage:
        """Build the RFC-style MIME message without opening a network connection."""

        mime_message = MIMEEmailMessage()
        mime_message["From"] = message.sender.value
        mime_message["To"] = ", ".join(
            formataddr((recipient.display_name or "", recipient.address.value))
            for recipient in message.recipients
        )
        if message.content.subject is not None:
            mime_message["Subject"] = message.content.subject
        mime_message["Message-ID"] = make_msgid()
        mime_message["X-PyCRMKit-Intent-ID"] = str(message.intent_id)
        if message.idempotency_key is not None:
            mime_message["X-PyCRMKit-Idempotency-Key"] = message.idempotency_key

        text_body = message.content.text_body
        html_body = message.content.html_body
        if text_body is not None and html_body is not None:
            mime_message.set_content(text_body)
            mime_message.add_alternative(html_body, subtype="html")
        elif text_body is not None:
            mime_message.set_content(text_body)
        else:
            assert html_body is not None
            mime_message.set_content(html_body, subtype="html")
        return mime_message

    def _send_message(self, message: MIMEEmailMessage) -> dict[str, tuple[int, bytes]]:
        context = ssl.create_default_context()
        if self.config.security is SMTPSecurity.TLS:
            with smtplib.SMTP_SSL(
                self.config.host,
                self.config.port,
                local_hostname=self.config.local_hostname,
                timeout=self.config.timeout,
                context=context,
            ) as client:
                self._authenticate(client)
                return client.send_message(message)

        with smtplib.SMTP(
            self.config.host,
            self.config.port,
            local_hostname=self.config.local_hostname,
            timeout=self.config.timeout,
        ) as client:
            if self.config.security is SMTPSecurity.STARTTLS:
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            self._authenticate(client)
            return client.send_message(message)

    def _authenticate(self, client: smtplib.SMTP) -> None:
        if self.config.username is not None:
            assert self.config.password is not None
            client.login(self.config.username, self.config.password)

    def _failed(
        self,
        code: str,
        exc: Exception,
        *,
        refused_recipient_count: int | None = None,
    ) -> EmailProviderResult:
        metadata: dict[str, object] = {
            "security": self.config.security.value,
            "error_type": type(exc).__name__,
        }
        smtp_code = getattr(exc, "smtp_code", None)
        if isinstance(smtp_code, int):
            metadata["smtp_code"] = smtp_code
        if refused_recipient_count is not None:
            metadata["refused_recipient_count"] = refused_recipient_count
        return EmailProviderResult(
            provider=self.provider_name,
            status=EmailDeliveryStatus.FAILED,
            failure_code=code,
            provider_metadata=metadata,
        )


__all__ = ["SMTPConfig", "SMTPEmailProvider", "SMTPSecurity"]
