"""Official in-memory Communication repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.communication import (
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttempt,
    DeliveryAttemptId,
    EmailDeliveryEvent,
)
from pycrmkit.communication.repository import CommunicationRepository
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.memory._state import _MemoryState


def _key(provider: str, value: str) -> tuple[str, str]:
    return provider.strip().casefold(), value.strip()


class MemoryCommunicationRepository(CommunicationRepository):
    """Copy-isolated Communication repository over one Memory state snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get_intent(self, intent_id: CommunicationIntentId) -> CommunicationIntent:
        value = self._state.communication_intents.get(intent_id)
        if value is None:
            raise NotFoundError(
                "communication intent not found",
                code="communication.intent.not_found",
            )
        return deepcopy(value)

    def find_intent_by_idempotency_key(
        self,
        key: str,
    ) -> CommunicationIntent | None:
        normalized = key.strip()
        for item in self._state.communication_intents.values():
            if item.idempotency_key == normalized:
                return deepcopy(item)
        return None

    def save_intent(self, intent: CommunicationIntent) -> None:
        if intent.idempotency_key is not None:
            old = self.find_intent_by_idempotency_key(intent.idempotency_key)
            if old is not None and old.id != intent.id:
                raise DuplicateError(
                    "duplicate communication idempotency key",
                    code="communication.intent.idempotency_key.duplicate",
                )
        self._state.communication_intents[intent.id] = deepcopy(intent)

    def get_attempt(self, attempt_id: DeliveryAttemptId) -> DeliveryAttempt:
        value = self._state.delivery_attempts.get(attempt_id)
        if value is None:
            raise NotFoundError(
                "delivery attempt not found",
                code="communication.delivery.not_found",
            )
        return deepcopy(value)

    def find_attempt_by_provider_message_id(
        self,
        provider: str,
        provider_message_id: str,
    ) -> DeliveryAttempt | None:
        target = _key(provider, provider_message_id)
        for item in self._state.delivery_attempts.values():
            if (
                item.provider is not None
                and item.provider_message_id is not None
                and _key(item.provider, item.provider_message_id) == target
            ):
                return deepcopy(item)
        return None

    def save_attempt(self, attempt: DeliveryAttempt) -> None:
        if attempt.provider is not None and attempt.provider_message_id is not None:
            old = self.find_attempt_by_provider_message_id(
                attempt.provider,
                attempt.provider_message_id,
            )
            if old is not None and old.id != attempt.id:
                raise DuplicateError(
                    "duplicate provider message id",
                    code="communication.delivery.provider_message_id.duplicate",
                )
        self._state.delivery_attempts[attempt.id] = deepcopy(attempt)

    def get_record(self, record_id: CommunicationRecordId) -> CommunicationRecord:
        value = self._state.communication_records.get(record_id)
        if value is None:
            raise NotFoundError(
                "communication record not found",
                code="communication.record.not_found",
            )
        return deepcopy(value)

    def find_record_by_intent(
        self,
        intent_id: CommunicationIntentId,
    ) -> CommunicationRecord | None:
        for item in self._state.communication_records.values():
            if item.intent_id == intent_id:
                return deepcopy(item)
        return None

    def find_record_by_attempt(
        self,
        attempt_id: DeliveryAttemptId,
    ) -> CommunicationRecord | None:
        for item in self._state.communication_records.values():
            if item.delivery_attempt_id == attempt_id:
                return deepcopy(item)
        return None

    def save_record(self, record: CommunicationRecord) -> None:
        if record.intent_id is not None:
            old = self.find_record_by_intent(record.intent_id)
            if old is not None and old.id != record.id:
                raise DuplicateError(
                    "communication intent already has a CRM record",
                    code="communication.record.intent.duplicate",
                )
        if record.delivery_attempt_id is not None:
            old = self.find_record_by_attempt(record.delivery_attempt_id)
            if old is not None and old.id != record.id:
                raise DuplicateError(
                    "delivery attempt already has a CRM record",
                    code="communication.record.attempt.duplicate",
                )
        self._state.communication_records[record.id] = deepcopy(record)

    def list_records_for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CommunicationRecord]:
        values = [
            deepcopy(item)
            for item in self._state.communication_records.values()
            if reference in item.references
        ]
        values.sort(key=lambda item: item.id)
        values.sort(key=lambda item: item.occurred_at, reverse=True)
        total = len(values)
        return Page(
            items=tuple(values[page.offset : page.offset + page.limit]),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def find_delivery_event_by_external_id(
        self,
        provider: str,
        external_event_id: str,
    ) -> EmailDeliveryEvent | None:
        target = _key(provider, external_event_id)
        for item in self._state.email_delivery_events.values():
            if (
                item.provider is not None
                and item.external_event_id is not None
                and _key(item.provider, item.external_event_id) == target
            ):
                return item
        return None

    def append_delivery_event(self, event: EmailDeliveryEvent) -> None:
        old = self._state.email_delivery_events.get(event.id)
        if old is not None:
            if old != event:
                raise DuplicateError(
                    "delivery event id contains different history",
                    code="communication.delivery_event.id.conflict",
                )
            return

        if event.provider is not None and event.external_event_id is not None:
            replay = self.find_delivery_event_by_external_id(
                event.provider,
                event.external_event_id,
            )
            if replay is not None:
                if replay != event:
                    raise DuplicateError(
                        "provider external event id contains different history",
                        code="communication.delivery_event.external_id.conflict",
                    )
                return

        self._state.email_delivery_events[event.id] = event

    def list_delivery_events_for_intent(
        self,
        intent_id: CommunicationIntentId,
        page: OffsetPageRequest,
    ) -> Page[EmailDeliveryEvent]:
        values = [
            item
            for item in self._state.email_delivery_events.values()
            if item.intent_id == intent_id
        ]
        values.sort(key=lambda item: item.id)
        values.sort(key=lambda item: item.occurred_at, reverse=True)
        total = len(values)
        return Page(
            items=tuple(values[page.offset : page.offset + page.limit]),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
