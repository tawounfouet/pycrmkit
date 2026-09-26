"""HTTP transport boundary for webhook delivery."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from pycrmkit.exceptions import IntegrationError, ValidationError
from pycrmkit.webhooks.entities import normalize_webhook_url


class WebhookTransportError(IntegrationError):
    """Normalized transport failure safe for retry policy and delivery logs."""


@dataclass(frozen=True, slots=True)
class WebhookRequest:
    """One outbound webhook HTTP request."""

    url: str
    body: bytes = field(repr=False)
    headers: Mapping[str, str]
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", normalize_webhook_url(self.url))
        if not isinstance(self.body, bytes):
            raise ValidationError(
                "webhook request body must be bytes",
                code="webhook.transport.body.invalid",
            )
        if self.timeout_seconds <= 0:
            raise ValidationError(
                "webhook timeout must be positive",
                code="webhook.transport.timeout.invalid",
            )
        object.__setattr__(self, "headers", dict(self.headers))


@dataclass(frozen=True, slots=True)
class WebhookResponse:
    """Response metadata retained by the delivery engine."""

    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.status_code) is not int or not 100 <= self.status_code <= 599:
            raise ValidationError(
                "webhook response status code is invalid",
                code="webhook.transport.status.invalid",
            )
        object.__setattr__(self, "headers", dict(self.headers))


@runtime_checkable
class WebhookTransport(Protocol):
    """Provider-neutral synchronous HTTP transport."""

    def send(self, request: WebhookRequest) -> WebhookResponse:
        ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


def _is_public_address(value: str) -> bool:
    return ipaddress.ip_address(value).is_global


@dataclass(slots=True)
class StdlibWebhookTransport(WebhookTransport):
    """Standard-library HTTP POST transport with conservative network policy."""

    allow_private_networks: bool = False

    def send(self, request: WebhookRequest) -> WebhookResponse:
        if not self.allow_private_networks:
            self._validate_public_destination(request.url)

        http_request = Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method="POST",
        )
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(http_request, timeout=request.timeout_seconds) as response:
                return WebhookResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as exc:
            return WebhookResponse(
                status_code=exc.code,
                headers=dict(exc.headers.items()) if exc.headers is not None else {},
            )
        except TimeoutError as exc:
            raise WebhookTransportError(
                "webhook request timed out",
                code="webhook.transport.timeout",
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise WebhookTransportError(
                    "webhook request timed out",
                    code="webhook.transport.timeout",
                ) from exc
            raise WebhookTransportError(
                "webhook network request failed",
                code="webhook.transport.network_error",
            ) from exc
        except OSError as exc:
            raise WebhookTransportError(
                "webhook network request failed",
                code="webhook.transport.network_error",
            ) from exc

    @staticmethod
    def _validate_public_destination(url: str) -> None:
        parsed = urlsplit(url)
        host = parsed.hostname
        if host is None:
            raise WebhookTransportError(
                "webhook destination is invalid",
                code="webhook.transport.destination_invalid",
            )

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            try:
                resolved = socket.getaddrinfo(
                    host,
                    port,
                    type=socket.SOCK_STREAM,
                )
            except OSError as exc:
                raise WebhookTransportError(
                    "webhook destination could not be resolved",
                    code="webhook.transport.dns_error",
                ) from exc
            addresses = {item[4][0] for item in resolved}
        else:
            addresses = {str(literal)}

        if not addresses or any(not _is_public_address(value) for value in addresses):
            raise WebhookTransportError(
                "webhook destination is not publicly routable",
                code="webhook.transport.destination_forbidden",
            )


__all__ = [
    "StdlibWebhookTransport",
    "WebhookRequest",
    "WebhookResponse",
    "WebhookTransport",
    "WebhookTransportError",
]
