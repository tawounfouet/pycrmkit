"""Persistence contract for Communication state and delivery history."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.communication.delivery import EmailDeliveryEvent
from pycrmkit.communication.entities import (
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttempt,
    DeliveryAttemptId,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference


@runtime_checkable
class CommunicationRepository(Protocol):
    """Backend-neutral repository for Communication state and history."""

    def get_intent(self, intent_id: CommunicationIntentId) -> CommunicationIntent:
        ...

    def find_intent_by_idempotency_key(
        self,
        key: str,
    ) -> CommunicationIntent | None:
        ...

    def save_intent(self, intent: CommunicationIntent) -> None:
        ...

    def get_attempt(self, attempt_id: DeliveryAttemptId) -> DeliveryAttempt:
        ...

    def find_attempt_by_provider_message_id(
        self,
        provider: str,
        provider_message_id: str,
    ) -> DeliveryAttempt | None:
        ...

    def save_attempt(self, attempt: DeliveryAttempt) -> None:
        ...

    def get_record(self, record_id: CommunicationRecordId) -> CommunicationRecord:
        ...

    def find_record_by_intent(
        self,
        intent_id: CommunicationIntentId,
    ) -> CommunicationRecord | None:
        ...

    def find_record_by_attempt(
        self,
        attempt_id: DeliveryAttemptId,
    ) -> CommunicationRecord | None:
        ...

    def save_record(self, record: CommunicationRecord) -> None:
        ...

    def list_records_for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CommunicationRecord]:
        ...

    def find_delivery_event_by_external_id(
        self,
        provider: str,
        external_event_id: str,
    ) -> EmailDeliveryEvent | None:
        ...

    def append_delivery_event(self, event: EmailDeliveryEvent) -> None:
        ...

    def list_delivery_events_for_intent(
        self,
        intent_id: CommunicationIntentId,
        page: OffsetPageRequest,
    ) -> Page[EmailDeliveryEvent]:
        ...
