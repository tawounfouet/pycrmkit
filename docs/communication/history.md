# Delivery Events & Communication History

PyCRMKit normalizes email lifecycle history into seven public event names:

```text
email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
```

Not every provider must support every downstream event.

## Sending

Configure CRM with an EmailProvider, sender, and optional TemplateRenderer. Then use crm.email.send with either provider-neutral CommunicationContent or EmailTemplate plus context.

The operation persists the intent, provider attempt, CRM record, queued/sent-or-failed history and Timeline projections in one Memory transaction. An idempotency key prevents repeat provider submission after a successful committed send.

## Provider callbacks

Use crm.email.record_delivery_event with provider name, provider message ID, normalized lifecycle type, provider occurrence time, and preferably an external event ID.

External event IDs provide idempotent callback replay. Events arriving out of chronological order remain in append-only history but do not regress the record's current delivery state.

## History

crm.email.for_contact and crm.email.for_organization return CommunicationRecord history. crm.email.delivery_history returns the normalized lifecycle events for one record.

The customer Timeline projects Communication events as kind communication while preserving Activity and Task entries as separate domains.
