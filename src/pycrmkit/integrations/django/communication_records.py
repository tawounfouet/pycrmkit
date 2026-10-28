"""Native Django record-level Communication persistence for Campaign linkage.

Only the CommunicationRecord lookup/save subset is provided here. This is
not a full CommunicationRepository for outbound intents, attempts or events.
"""

from __future__ import annotations

from copy import deepcopy

from django.db import IntegrityError, transaction

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationDirection,
    CommunicationIntentId,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttemptId,
    EmailDeliveryEventType,
)
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.integrations.django.campaign_codec import aware, entity_reference
from pycrmkit.integrations.django.models import CommunicationRecordModel


def _hydrate(model: CommunicationRecordModel) -> CommunicationRecord:
    return CommunicationRecord(
        id=CommunicationRecordId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        channel=CommunicationChannel(model.channel),
        direction=CommunicationDirection(model.direction),
        occurred_at=aware(model.occurred_at),
        counterparties=tuple(
            CommunicationAddress(
                CommunicationChannel(item["channel"]), item["value"]
            )
            for item in model.counterparties_json
        ),
        subject=model.subject,
        references=tuple(
            entity_reference(item["kind"], item["id"])
            for item in model.references_json
        ),
        intent_id=(
            CommunicationIntentId.parse(model.intent_id)
            if model.intent_id is not None
            else None
        ),
        delivery_attempt_id=(
            DeliveryAttemptId.parse(model.delivery_attempt_id)
            if model.delivery_attempt_id is not None
            else None
        ),
        external_id=model.external_id,
        delivery_status=(
            EmailDeliveryEventType(model.delivery_status)
            if model.delivery_status is not None
            else None
        ),
        last_delivery_event_at=aware(model.last_delivery_event_at),
        metadata=deepcopy(dict(model.metadata_json or {})),
    )


class DjangoCommunicationRecordStore:
    """Transactional native record lookup/save, sufficient for Campaign linkage."""

    def get_record(self, record_id: CommunicationRecordId) -> CommunicationRecord:
        model = CommunicationRecordModel.objects.filter(pk=str(record_id)).first()
        if model is None:
            raise NotFoundError(
                "communication record not found",
                code="communication.record.not_found",
            )
        return _hydrate(model)

    def save_record(self, record: CommunicationRecord) -> None:
        if record.intent_id is not None:
            used = CommunicationRecordModel.objects.filter(
                intent_id=str(record.intent_id)
            ).exclude(pk=str(record.id)).exists()
            if used:
                raise DuplicateError(
                    "communication intent already has a CRM record",
                    code="communication.record.intent.duplicate",
                )
        if record.delivery_attempt_id is not None:
            used = CommunicationRecordModel.objects.filter(
                delivery_attempt_id=str(record.delivery_attempt_id)
            ).exclude(pk=str(record.id)).exists()
            if used:
                raise DuplicateError(
                    "delivery attempt already has a CRM record",
                    code="communication.record.attempt.duplicate",
                )

        values = {
            "channel": record.channel.value,
            "direction": record.direction.value,
            "occurred_at": record.occurred_at,
            "counterparties_json": [
                {"channel": address.channel.value, "value": address.value}
                for address in record.counterparties
            ],
            "references_json": [
                {"kind": ref.kind, "id": str(ref.id)}
                for ref in record.references
            ],
            "subject": record.subject,
            "intent_id": str(record.intent_id) if record.intent_id else None,
            "delivery_attempt_id": (
                str(record.delivery_attempt_id)
                if record.delivery_attempt_id else None
            ),
            "external_id": record.external_id,
            "delivery_status": (
                record.delivery_status.value if record.delivery_status else None
            ),
            "last_delivery_event_at": record.last_delivery_event_at,
            "metadata_json": deepcopy(dict(record.metadata)),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        try:
            with transaction.atomic():
                CommunicationRecordModel.objects.update_or_create(
                    pk=str(record.id), defaults=values
                )
        except IntegrityError as error:
            raise DuplicateError(
                "communication record identity or linked reference already exists",
                code="communication.record.conflict",
            ) from error


__all__ = ["DjangoCommunicationRecordStore"]
