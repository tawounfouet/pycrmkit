"""Transactional email facade and delivery-history ingestion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationDirection,
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationRecord,
    CommunicationRecordId,
    CommunicationRecipient,
    DeliveryAttemptStatus,
    EmailDeliveryEvent,
    EmailDeliveryEventId,
    EmailDeliveryEventType,
    EmailDeliveryService,
    EmailProvider,
    EmailTemplate,
    TemplateRenderer,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import (
    DuplicateError,
    IntegrationError,
    NotFoundError,
    ValidationError,
)
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.organizations import OrganizationId

_CALLBACK_TYPES = {
    EmailDeliveryEventType.DELIVERED,
    EmailDeliveryEventType.OPENED,
    EmailDeliveryEventType.CLICKED,
    EmailDeliveryEventType.BOUNCED,
    EmailDeliveryEventType.FAILED,
}


class EmailAPI:
    """Outbound email and provider delivery-history namespace."""

    def __init__(
        self,
        runtime: CRMRuntime,
        *,
        provider: EmailProvider | None = None,
        sender: CommunicationAddress | None = None,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self._runtime = runtime
        self._provider = provider
        self._sender = sender
        self._renderer = renderer

    def send(
        self,
        *,
        to: Sequence[CommunicationRecipient],
        content: CommunicationContent | None = None,
        template: EmailTemplate | None = None,
        template_context: Mapping[str, object] | None = None,
        sender: CommunicationAddress | None = None,
        references: Sequence[EntityReference] = (),
        idempotency_key: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CommunicationRecord:
        """Send and persist one outbound email as an atomic CRM operation."""

        if self._provider is None:
            raise IntegrationError(
                "email provider is not configured",
                code="communication.email.provider.required",
            )
        effective_sender = sender or self._sender
        if effective_sender is None:
            raise ValidationError(
                "email sender is required",
                code="communication.email.sender.required",
            )

        resolved = self._resolve_content(content, template, template_context)
        recipients = tuple(to)
        recipient_references = tuple(
            recipient.reference
            for recipient in recipients
            if recipient.reference is not None
        )
        refs = tuple(dict.fromkeys((*recipient_references, *references)))

        with self._runtime.uow_factory() as uow:
            if idempotency_key is not None:
                old = uow.communications.find_intent_by_idempotency_key(idempotency_key)
                if old is not None:
                    record = uow.communications.find_record_by_intent(old.id)
                    if record is None:
                        raise DuplicateError(
                            "incomplete idempotent email replay",
                            code="communication.email.idempotency.incomplete",
                        )
                    return record

            now = self._runtime.clock.now()
            intent = CommunicationIntent(
                id=self._runtime.id_factory.new(CommunicationIntentId),
                created_at=now,
                updated_at=now,
                channel=CommunicationChannel.EMAIL,
                recipients=recipients,
                content=resolved,
                references=refs,
                idempotency_key=idempotency_key,
                metadata=dict(metadata or {}),
            )
            intent.queue(now)
            uow.communications.save_intent(intent)

            queued = EmailDeliveryEvent(
                id=self._runtime.id_factory.new(EmailDeliveryEventId),
                intent_id=intent.id,
                event_type=EmailDeliveryEventType.QUEUED,
                occurred_at=intent.queued_at or now,
                recorded_at=now,
                metadata={"source": "pycrmkit"},
            )
            uow.communications.append_delivery_event(queued)
            self._runtime.record_change(
                uow,
                event_type="email.queued",
                aggregate_type="communication_intent",
                aggregate_id=intent.id,
                payload={
                    "delivery_status": "queued",
                    "business_occurred_at": queued.occurred_at.isoformat(),
                },
            )

            attempt = EmailDeliveryService(
                provider=self._provider,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).send(intent, sender=effective_sender)
            uow.communications.save_attempt(attempt)

            state = (
                EmailDeliveryEventType.SENT
                if attempt.status is DeliveryAttemptStatus.ACCEPTED
                else EmailDeliveryEventType.FAILED
            )
            occurred = attempt.completed_at or attempt.attempted_at
            record = CommunicationRecord(
                id=self._runtime.id_factory.new(CommunicationRecordId),
                created_at=occurred,
                updated_at=occurred,
                channel=CommunicationChannel.EMAIL,
                direction=CommunicationDirection.OUTBOUND,
                occurred_at=occurred,
                counterparties=tuple(recipient.address for recipient in recipients),
                subject=resolved.subject,
                references=refs,
                intent_id=intent.id,
                delivery_attempt_id=attempt.id,
                external_id=attempt.provider_message_id,
                delivery_status=state,
                last_delivery_event_at=occurred,
                metadata={"provider": attempt.provider},
            )
            uow.communications.save_record(record)

            outcome = EmailDeliveryEvent(
                id=self._runtime.id_factory.new(EmailDeliveryEventId),
                intent_id=intent.id,
                event_type=state,
                occurred_at=occurred,
                recorded_at=self._runtime.clock.now(),
                delivery_attempt_id=attempt.id,
                provider=attempt.provider,
                provider_message_id=attempt.provider_message_id,
                failure_code=attempt.failure_code,
                metadata=dict(attempt.metadata),
            )
            uow.communications.append_delivery_event(outcome)
            self._runtime.record_change(
                uow,
                event_type=state.event_name,
                aggregate_type="communication_record",
                aggregate_id=record.id,
                payload={
                    "delivery_status": state.value,
                    "provider": attempt.provider,
                    "business_occurred_at": occurred.isoformat(),
                },
            )
            uow.commit()
            return record

    def record_delivery_event(
        self,
        *,
        provider: str,
        provider_message_id: str,
        event_type: EmailDeliveryEventType | str,
        occurred_at: datetime,
        external_event_id: str | None = None,
        recipient: CommunicationAddress | None = None,
        failure_code: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> EmailDeliveryEvent:
        """Persist one normalized downstream provider callback."""

        parsed = EmailDeliveryEventType(event_type)
        if parsed not in _CALLBACK_TYPES:
            raise ValidationError(
                "event type is not a downstream callback",
                code="communication.email.callback.type.invalid",
            )

        with self._runtime.uow_factory() as uow:
            if external_event_id is not None:
                replay = uow.communications.find_delivery_event_by_external_id(
                    provider,
                    external_event_id,
                )
                if replay is not None:
                    if (
                        replay.event_type is parsed
                        and replay.provider_message_id == provider_message_id
                    ):
                        return replay
                    raise DuplicateError(
                        "provider callback id conflicts with existing event",
                        code="communication.delivery_event.external_id.conflict",
                    )

            attempt = uow.communications.find_attempt_by_provider_message_id(
                provider,
                provider_message_id,
            )
            if attempt is None:
                raise NotFoundError(
                    "provider message id is unknown",
                    code="communication.delivery.provider_message_not_found",
                )
            record = uow.communications.find_record_by_attempt(attempt.id)
            if record is None:
                raise NotFoundError(
                    "communication record for attempt not found",
                    code="communication.record.attempt_not_found",
                )

            recorded = self._runtime.clock.now()
            event = EmailDeliveryEvent(
                id=self._runtime.id_factory.new(EmailDeliveryEventId),
                intent_id=attempt.intent_id,
                event_type=parsed,
                occurred_at=occurred_at,
                recorded_at=recorded,
                delivery_attempt_id=attempt.id,
                provider=attempt.provider,
                provider_message_id=attempt.provider_message_id,
                external_event_id=external_event_id,
                recipient=recipient,
                failure_code=failure_code,
                metadata=dict(metadata or {}),
            )
            uow.communications.append_delivery_event(event)
            record.apply_delivery_event(
                parsed,
                occurred_at=event.occurred_at,
                recorded_at=recorded,
            )
            uow.communications.save_record(record)
            self._runtime.record_change(
                uow,
                event_type=parsed.event_name,
                aggregate_type="communication_record",
                aggregate_id=record.id,
                payload={
                    "delivery_status": parsed.value,
                    "provider": attempt.provider,
                    "business_occurred_at": event.occurred_at.isoformat(),
                },
            )
            uow.commit()
            return event

    def get(self, record_id: CommunicationRecordId) -> CommunicationRecord:
        with self._runtime.uow_factory() as uow:
            return uow.communications.get_record(record_id)

    def for_contact(
        self,
        contact_id: ContactId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CommunicationRecord]:
        return self._for_reference(EntityReference("contact", contact_id), page)

    def for_organization(
        self,
        organization_id: OrganizationId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CommunicationRecord]:
        return self._for_reference(
            EntityReference("organization", organization_id),
            page,
        )

    def delivery_history(
        self,
        record_id: CommunicationRecordId,
        page: OffsetPageRequest | None = None,
    ) -> Page[EmailDeliveryEvent]:
        request = page or OffsetPageRequest()
        with self._runtime.uow_factory() as uow:
            record = uow.communications.get_record(record_id)
            if record.intent_id is None:
                return Page(
                    items=(),
                    limit=request.limit,
                    offset=request.offset,
                    total=0,
                )
            return uow.communications.list_delivery_events_for_intent(
                record.intent_id,
                request,
            )

    def _for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest | None,
    ) -> Page[CommunicationRecord]:
        with self._runtime.uow_factory() as uow:
            return uow.communications.list_records_for_reference(
                reference,
                page or OffsetPageRequest(),
            )

    def _resolve_content(
        self,
        content: CommunicationContent | None,
        template: EmailTemplate | None,
        context: Mapping[str, object] | None,
    ) -> CommunicationContent:
        if (content is None) == (template is None):
            raise ValidationError(
                "provide exactly one of content or template",
                code="communication.email.content.choice_invalid",
            )
        if content is not None:
            return content
        assert template is not None
        if self._renderer is None:
            raise IntegrationError(
                "template renderer is not configured",
                code="communication.email.template.renderer_required",
            )
        return self._renderer.render(template, context or {})
