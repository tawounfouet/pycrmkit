# Email Provider Protocol

PyCRMKit `0.4.0a2` introduces the transport seam used by concrete email adapters.

## Contract

Every provider implements:

```python
class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> EmailProviderResult:
        ...
```

The domain does not import SMTP, Resend, HTTP clients, credentials, or provider SDKs.

## EmailMessage

`EmailMessage` is immutable and contains only provider-relevant data:

- originating `CommunicationIntentId`;
- sender address;
- recipients;
- provider-neutral content;
- optional idempotency key;
- JSON-compatible metadata.

CRM entity references are deliberately not copied into the provider message.

## EmailProviderResult

The normalized result contains:

- `provider`;
- `status`: `accepted` or `failed`;
- optional `provider_message_id`;
- immutable provider metadata;
- optional `failure_code`.

An accepted result cannot carry a failure code. A failed result cannot carry a provider message ID.

## EmailDeliveryService

`EmailDeliveryService` accepts a queued email `CommunicationIntent`, builds an `EmailMessage`, invokes the configured provider, then converts the normalized result into a `DeliveryAttempt`.

It deliberately does not:

- persist the attempt;
- mark the intent as delivered;
- emit delivery/open/click/bounce events;
- retry automatically;
- choose SMTP versus Resend.

Those responsibilities belong to later milestones.

## Example

```python
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    EmailDeliveryService,
    EmailDeliveryStatus,
    EmailProviderResult,
)

class MyProvider:
    def send(self, message):
        return EmailProviderResult(
            provider="my-provider",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="provider-123",
        )

service = EmailDeliveryService(provider=MyProvider())
attempt = service.send(
    queued_intent,
    sender=CommunicationAddress(
        CommunicationChannel.EMAIL,
        "sales@example.com",
    ),
)
```

Concrete provider adapters begin in `0.4.0b1`.
