# Communication Domain

PyCRMKit `0.4.0a1` introduces the provider-agnostic foundation for CRM communications.

The architectural boundary is explicit:

```text
CommunicationIntent
    ↓
DeliveryAttempt
    ↓
CommunicationRecord
```

These concepts deliberately do **not** mean the same thing.

## Communication intent

`CommunicationIntent` represents what the CRM wants to communicate before a transport provider is involved. The current alpha is email-first and exposes normalized recipients, provider-neutral content, generic CRM references, optional idempotency metadata, and explicit draft/queued/cancelled lifecycle semantics.

An intent is outbound in this initial foundation. Inbound history is represented by CRM records and can later be populated by provider/webhook integrations.

## Delivery attempt

`DeliveryAttempt` represents one attempt to hand a queued intent to a provider or transport:

```text
pending
  ├── accepted
  └── failed
```

`accepted` means that the provider or transport accepted the message. It does **not** mean that the recipient mailbox delivered, opened, or clicked it.

## CRM communication record

`CommunicationRecord` is the relationship-history representation consumed by CRM read models. It stores channel/direction, business occurrence time, counterparties, subject, CRM references, optional intent/delivery-attempt provenance, external identity, and metadata.

Message bodies are deliberately not duplicated into the record. The intent owns message content; the CRM record owns relationship-history context.

## What 0.4.0a1 does not include

This release does not provide `crm.email.send(...)`, an `EmailProvider` protocol, SMTP, Resend, templates, provider network calls, communication repositories, delivery webhooks, or open/click/bounce ingestion.

Those capabilities are intentionally split across the remaining `0.4.x` prereleases.

## Next milestone

`0.4.0a2` adds the Email Provider Protocol and provider-independent email send service boundary.
