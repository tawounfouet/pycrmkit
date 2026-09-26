"""SQLAlchemy CommunicationRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from pycrmkit.communication import (
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttempt,
    DeliveryAttemptId,
    EmailDeliveryEvent,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import (
    communication_intent_from_model,
    communication_intent_to_model,
    communication_record_from_model,
    communication_record_to_model,
    delivery_attempt_from_model,
    delivery_attempt_to_model,
    email_delivery_event_from_model,
    email_delivery_event_to_model,
)
from pycrmkit.storage.sqlalchemy.models.communication import (
    CommunicationCounterpartyModel,
    CommunicationIntentModel,
    CommunicationIntentReferenceModel,
    CommunicationRecipientModel,
    CommunicationRecordModel,
    CommunicationRecordReferenceModel,
    DeliveryAttemptModel,
    EmailDeliveryEventModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


def _normalized_pair(
    provider: str,
    value: str,
) -> tuple[str, str]:
    return provider.strip().casefold(), value.strip()


class SQLAlchemyCommunicationRepository:
    """SQLAlchemy adapter for communication intent, delivery and CRM history state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_intent(
        self,
        intent_id: CommunicationIntentId,
    ) -> CommunicationIntent:
        model = self.session.get(
            CommunicationIntentModel,
            str(intent_id),
        )
        if model is None:
            raise NotFoundError(
                "communication intent not found",
                code="communication.intent.not_found",
            )
        return self._hydrate_intent(model)

    def find_intent_by_idempotency_key(
        self,
        key: str,
    ) -> CommunicationIntent | None:
        model = self.session.scalar(
            select(CommunicationIntentModel).where(
                CommunicationIntentModel.idempotency_key
                == key.strip()
            )
        )
        return (
            None
            if model is None
            else self._hydrate_intent(model)
        )

    def save_intent(
        self,
        intent: CommunicationIntent,
    ) -> None:
        if intent.idempotency_key is not None:
            with self.session.no_autoflush:
                old = self.find_intent_by_idempotency_key(
                    intent.idempotency_key
                )
            if old is not None and old.id != intent.id:
                raise DuplicateError(
                    "duplicate communication idempotency key",
                    code="communication.intent.idempotency_key.duplicate",
                )
        model = self.session.get(
            CommunicationIntentModel,
            str(intent.id),
        )
        target = communication_intent_to_model(
            intent,
            model,
        )
        if model is None:
            self.session.add(target)

        key = str(intent.id)
        self.session.execute(
            delete(CommunicationRecipientModel).where(
                CommunicationRecipientModel.intent_id == key
            )
        )
        self.session.execute(
            delete(CommunicationIntentReferenceModel).where(
                CommunicationIntentReferenceModel.intent_id
                == key
            )
        )
        self.session.add_all(
            [
                CommunicationRecipientModel(
                    intent_id=key,
                    position=position,
                    channel=recipient.address.channel.value,
                    value=recipient.address.value,
                    normalized=recipient.address.normalized,
                    display_name=recipient.display_name,
                    reference_kind=(
                        recipient.reference.kind
                        if recipient.reference
                        else None
                    ),
                    reference_id=(
                        str(recipient.reference.id)
                        if recipient.reference
                        else None
                    ),
                )
                for position, recipient in enumerate(
                    intent.recipients
                )
            ]
        )
        self.session.add_all(
            [
                CommunicationIntentReferenceModel(
                    intent_id=key,
                    position=position,
                    entity_kind=reference.kind,
                    entity_id=str(reference.id),
                )
                for position, reference in enumerate(
                    intent.references
                )
            ]
        )

    def get_attempt(
        self,
        attempt_id: DeliveryAttemptId,
    ) -> DeliveryAttempt:
        model = self.session.get(
            DeliveryAttemptModel,
            str(attempt_id),
        )
        if model is None:
            raise NotFoundError(
                "delivery attempt not found",
                code="communication.delivery.not_found",
            )
        return delivery_attempt_from_model(model)

    def find_attempt_by_provider_message_id(
        self,
        provider: str,
        provider_message_id: str,
    ) -> DeliveryAttempt | None:
        normalized_provider, message_id = _normalized_pair(
            provider,
            provider_message_id,
        )
        model = self.session.scalar(
            select(DeliveryAttemptModel).where(
                func.lower(DeliveryAttemptModel.provider)
                == normalized_provider,
                DeliveryAttemptModel.provider_message_id
                == message_id,
            )
        )
        return (
            None
            if model is None
            else delivery_attempt_from_model(model)
        )

    def save_attempt(
        self,
        attempt: DeliveryAttempt,
    ) -> None:
        if (
            attempt.provider is not None
            and attempt.provider_message_id is not None
        ):
            with self.session.no_autoflush:
                old = (
                    self.find_attempt_by_provider_message_id(
                        attempt.provider,
                        attempt.provider_message_id,
                    )
                )
            if old is not None and old.id != attempt.id:
                raise DuplicateError(
                    "duplicate provider message id",
                    code=(
                        "communication.delivery."
                        "provider_message_id.duplicate"
                    ),
                )
        model = self.session.get(
            DeliveryAttemptModel,
            str(attempt.id),
        )
        target = delivery_attempt_to_model(
            attempt,
            model,
        )
        if model is None:
            self.session.add(target)

    def get_record(
        self,
        record_id: CommunicationRecordId,
    ) -> CommunicationRecord:
        model = self.session.get(
            CommunicationRecordModel,
            str(record_id),
        )
        if model is None:
            raise NotFoundError(
                "communication record not found",
                code="communication.record.not_found",
            )
        return self._hydrate_record(model)

    def find_record_by_intent(
        self,
        intent_id: CommunicationIntentId,
    ) -> CommunicationRecord | None:
        model = self.session.scalar(
            select(CommunicationRecordModel).where(
                CommunicationRecordModel.intent_id
                == str(intent_id)
            )
        )
        return (
            None
            if model is None
            else self._hydrate_record(model)
        )

    def find_record_by_attempt(
        self,
        attempt_id: DeliveryAttemptId,
    ) -> CommunicationRecord | None:
        model = self.session.scalar(
            select(CommunicationRecordModel).where(
                CommunicationRecordModel.delivery_attempt_id
                == str(attempt_id)
            )
        )
        return (
            None
            if model is None
            else self._hydrate_record(model)
        )

    def save_record(
        self,
        record: CommunicationRecord,
    ) -> None:
        if record.intent_id is not None:
            with self.session.no_autoflush:
                old = self.find_record_by_intent(
                    record.intent_id
                )
            if old is not None and old.id != record.id:
                raise DuplicateError(
                    "communication intent already has a CRM record",
                    code="communication.record.intent.duplicate",
                )
        if record.delivery_attempt_id is not None:
            with self.session.no_autoflush:
                old = self.find_record_by_attempt(
                    record.delivery_attempt_id
                )
            if old is not None and old.id != record.id:
                raise DuplicateError(
                    "delivery attempt already has a CRM record",
                    code="communication.record.attempt.duplicate",
                )
        model = self.session.get(
            CommunicationRecordModel,
            str(record.id),
        )
        target = communication_record_to_model(
            record,
            model,
        )
        if model is None:
            self.session.add(target)

        key = str(record.id)
        self.session.execute(
            delete(CommunicationCounterpartyModel).where(
                CommunicationCounterpartyModel.record_id
                == key
            )
        )
        self.session.execute(
            delete(CommunicationRecordReferenceModel).where(
                CommunicationRecordReferenceModel.record_id
                == key
            )
        )
        self.session.add_all(
            [
                CommunicationCounterpartyModel(
                    record_id=key,
                    position=position,
                    channel=address.channel.value,
                    value=address.value,
                    normalized=address.normalized,
                )
                for position, address in enumerate(
                    record.counterparties
                )
            ]
        )
        self.session.add_all(
            [
                CommunicationRecordReferenceModel(
                    record_id=key,
                    position=position,
                    entity_kind=reference.kind,
                    entity_id=str(reference.id),
                )
                for position, reference in enumerate(
                    record.references
                )
            ]
        )

    def list_records_for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CommunicationRecord]:
        statement = (
            select(CommunicationRecordModel)
            .where(
                exists(
                    select(
                        CommunicationRecordReferenceModel.id
                    ).where(
                        CommunicationRecordReferenceModel.record_id
                        == CommunicationRecordModel.id,
                        CommunicationRecordReferenceModel.entity_kind
                        == reference.kind,
                        CommunicationRecordReferenceModel.entity_id
                        == str(reference.id),
                    )
                )
            )
            .order_by(
                CommunicationRecordModel.occurred_at.desc(),
                CommunicationRecordModel.id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate_record,
        )

    def find_delivery_event_by_external_id(
        self,
        provider: str,
        external_event_id: str,
    ) -> EmailDeliveryEvent | None:
        normalized_provider, external_id = _normalized_pair(
            provider,
            external_event_id,
        )
        model = self.session.scalar(
            select(EmailDeliveryEventModel).where(
                func.lower(EmailDeliveryEventModel.provider)
                == normalized_provider,
                EmailDeliveryEventModel.external_event_id
                == external_id,
            )
        )
        return (
            None
            if model is None
            else email_delivery_event_from_model(model)
        )

    def append_delivery_event(
        self,
        event: EmailDeliveryEvent,
    ) -> None:
        old_model = self.session.get(
            EmailDeliveryEventModel,
            str(event.id),
        )
        if old_model is not None:
            old = email_delivery_event_from_model(old_model)
            if old != event:
                raise DuplicateError(
                    "delivery event id contains different history",
                    code="communication.delivery_event.id.conflict",
                )
            return
        if (
            event.provider is not None
            and event.external_event_id is not None
        ):
            with self.session.no_autoflush:
                replay = (
                    self.find_delivery_event_by_external_id(
                        event.provider,
                        event.external_event_id,
                    )
                )
            if replay is not None:
                if replay != event:
                    raise DuplicateError(
                        "provider external event id contains different history",
                        code=(
                            "communication.delivery_event."
                            "external_id.conflict"
                        ),
                    )
                return
        self.session.add(
            email_delivery_event_to_model(event)
        )

    def list_delivery_events_for_intent(
        self,
        intent_id: CommunicationIntentId,
        page: OffsetPageRequest,
    ) -> Page[EmailDeliveryEvent]:
        statement = (
            select(EmailDeliveryEventModel)
            .where(
                EmailDeliveryEventModel.intent_id
                == str(intent_id)
            )
            .order_by(
                EmailDeliveryEventModel.occurred_at.desc(),
                EmailDeliveryEventModel.id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            email_delivery_event_from_model,
        )

    def _hydrate_intent(
        self,
        model: CommunicationIntentModel,
    ) -> CommunicationIntent:
        recipients = list(
            self.session.scalars(
                select(CommunicationRecipientModel)
                .where(
                    CommunicationRecipientModel.intent_id
                    == model.id
                )
                .order_by(
                    CommunicationRecipientModel.position.asc(),
                    CommunicationRecipientModel.id.asc(),
                )
            )
        )
        references = list(
            self.session.scalars(
                select(CommunicationIntentReferenceModel)
                .where(
                    CommunicationIntentReferenceModel.intent_id
                    == model.id
                )
                .order_by(
                    CommunicationIntentReferenceModel.position.asc(),
                    CommunicationIntentReferenceModel.id.asc(),
                )
            )
        )
        return communication_intent_from_model(
            model,
            recipients,
            references,
        )

    def _hydrate_record(
        self,
        model: CommunicationRecordModel,
    ) -> CommunicationRecord:
        counterparties = list(
            self.session.scalars(
                select(CommunicationCounterpartyModel)
                .where(
                    CommunicationCounterpartyModel.record_id
                    == model.id
                )
                .order_by(
                    CommunicationCounterpartyModel.position.asc(),
                    CommunicationCounterpartyModel.id.asc(),
                )
            )
        )
        references = list(
            self.session.scalars(
                select(CommunicationRecordReferenceModel)
                .where(
                    CommunicationRecordReferenceModel.record_id
                    == model.id
                )
                .order_by(
                    CommunicationRecordReferenceModel.position.asc(),
                    CommunicationRecordReferenceModel.id.asc(),
                )
            )
        )
        return communication_record_from_model(
            model,
            counterparties,
            references,
        )
