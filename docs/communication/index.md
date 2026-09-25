# Communication Domain

PyCRMKit `0.4.x` separates CRM communication semantics from transport providers:

```text
CommunicationIntent
    ↓
EmailDeliveryService
    ↓
EmailProvider
    ↓
DeliveryAttempt
    ↓
CommunicationRecord
    ↓
EmailDeliveryEvent history
    ↓
TimelineEntryKind.COMMUNICATION
```

These concepts deliberately do **not** mean the same thing.

## Communication intent

`CommunicationIntent` represents what the CRM wants to communicate before a transport provider is involved. The current line is email-first and exposes normalized recipients, provider-neutral content, generic CRM references, optional idempotency metadata, and explicit draft/queued/cancelled lifecycle semantics.

## Provider boundary

Starting with `0.4.0a2`, email transport is expressed through `EmailProvider.send(EmailMessage)`.

Providers return a normalized `EmailProviderResult` carrying:

- provider name;
- immediate transport status;
- optional `provider_message_id`;
- provider metadata;
- optional failure code.

`accepted` means the provider accepted the message for transport. It does **not** mean the recipient mailbox delivered, opened, or clicked it.

See [Email Provider Protocol](email-provider.md).

## CRM communication record

`CommunicationRecord` remains the relationship-history representation consumed by CRM read models. Message bodies are deliberately not duplicated into the record.

## Stable 0.4.x scope

The stable line includes provider-neutral templates, the stdlib SMTP adapter,
the optional Resend adapter, normalized delivery/open/click/bounce/failure
history, Memory persistence, `crm.email`, and Communication Timeline
projection.

Communication is not mirrored into `Activity(type="email")`. Its source of
truth remains `CommunicationRecord`, while Timeline provides the
cross-domain customer-history view.

Durable webhooks/event delivery remain part of `0.5.x`; production
SQLAlchemy/PostgreSQL persistence remains part of `0.6.x`.
