"""Explicit Domain <-> SQLAlchemy model mappings for persistence adapters."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, overload

from pycrmkit.activities import (
    Activity,
    ActivityDirection,
    ActivityId,
    ActivityParticipant,
    ActivityType,
)
from pycrmkit.audit import AuditEntry, AuditEntryId
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationDirection,
    CommunicationIntent,
    CommunicationIntentId,
    CommunicationIntentStatus,
    CommunicationRecipient,
    CommunicationRecord,
    CommunicationRecordId,
    DeliveryAttempt,
    DeliveryAttemptId,
    DeliveryAttemptStatus,
    EmailDeliveryEvent,
    EmailDeliveryEventId,
    EmailDeliveryEventType,
)
from pycrmkit.contacts import (
    Address,
    Contact,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactStatus,
    VerificationState,
)
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldOption,
    CustomFieldType,
    CustomFieldValue,
    CustomFieldValueId,
)
from pycrmkit.leads import Lead, LeadId, LeadStatus
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityStatus
from pycrmkit.organizations import (
    Organization,
    OrganizationAddress,
    OrganizationDomain,
    OrganizationId,
    OrganizationStatus,
)
from pycrmkit.pipelines import Pipeline, Stage, StageOutcome, StageTransition
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipEntityKind,
    RelationshipId,
    RelationshipType,
)
from pycrmkit.storage.sqlalchemy.models.activity import (
    ActivityModel,
    ActivityParticipantModel,
    ActivityReferenceModel,
)
from pycrmkit.storage.sqlalchemy.models.audit import AuditEntryModel
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
from pycrmkit.storage.sqlalchemy.models.contact import (
    ContactAddressModel,
    ContactEmailModel,
    ContactModel,
    ContactPhoneModel,
)
from pycrmkit.storage.sqlalchemy.models.custom_field import (
    CustomFieldDefinitionModel,
    CustomFieldValueModel,
)
from pycrmkit.storage.sqlalchemy.models.lead import LeadModel
from pycrmkit.storage.sqlalchemy.models.opportunity import OpportunityModel
from pycrmkit.storage.sqlalchemy.models.organization import (
    OrganizationAddressModel,
    OrganizationDomainModel,
    OrganizationModel,
)
from pycrmkit.storage.sqlalchemy.models.pipeline import (
    PipelineModel,
    PipelineStageModel,
    PipelineTransitionModel,
)
from pycrmkit.storage.sqlalchemy.models.relationship import RelationshipModel
from pycrmkit.storage.sqlalchemy.models.tag import TagAssignmentModel, TagModel
from pycrmkit.storage.sqlalchemy.models.task import TaskModel, TaskReferenceModel
from pycrmkit.storage.sqlalchemy.models.timeline import TimelineEntryModel, TimelineReferenceModel
from pycrmkit.storage.sqlalchemy.models.webhook import (
    WebhookDeliveryAttemptModel,
    WebhookDeliveryModel,
    WebhookSubscriptionEventModel,
    WebhookSubscriptionModel,
)
from pycrmkit.tags import Tag, TagAssignment, TagAssignmentId, TagId, TagName
from pycrmkit.tasks import Task, TaskId, TaskPriority, TaskStatus
from pycrmkit.timeline import TimelineEntry, TimelineEntryId, TimelineEntryKind
from pycrmkit.webhooks import (
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryAttemptOutcome,
    WebhookDeliveryId,
    WebhookDeliveryState,
    WebhookSubscription,
    WebhookSubscriptionId,
)


@overload
def aware(value: datetime) -> datetime: ...


@overload
def aware(value: None) -> None: ...


def aware(value: datetime | None) -> datetime | None:
    """Normalize DB-returned timestamps, including SQLite naive values, to UTC."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def entity_reference(
    kind: str,
    identifier: str,
    id_type_name: str | None = None,
) -> EntityReference:
    """Restore a persisted entity reference without erasing its typed ID class."""

    known_types: tuple[type[UUIDId], ...] = (
        UUIDId,
        EntityId,
        ActivityId,
        CommunicationIntentId,
        CommunicationRecordId,
        ContactId,
        CustomFieldDefinitionId,
        CustomFieldValueId,
        DeliveryAttemptId,
        LeadId,
        OpportunityId,
        OrganizationId,
        RelationshipId,
        TagId,
        TagAssignmentId,
        TaskId,
        TimelineEntryId,
        WebhookDeliveryId,
        WebhookSubscriptionId,
    )
    by_name = {id_type.__name__: id_type for id_type in known_types}
    by_kind: dict[str, type[UUIDId]] = {
        "activity": ActivityId,
        "communication_intent": CommunicationIntentId,
        "communication_record": CommunicationRecordId,
        "contact": ContactId,
        "custom_field_definition": CustomFieldDefinitionId,
        "custom_field_value": CustomFieldValueId,
        "delivery_attempt": DeliveryAttemptId,
        "lead": LeadId,
        "opportunity": OpportunityId,
        "organization": OrganizationId,
        "relationship": RelationshipId,
        "tag": TagId,
        "tag_assignment": TagAssignmentId,
        "task": TaskId,
        "timeline_entry": TimelineEntryId,
        "webhook_delivery": WebhookDeliveryId,
        "webhook_subscription": WebhookSubscriptionId,
    }
    id_type = by_name.get(id_type_name) if id_type_name is not None else None
    id_type = id_type or by_kind.get(kind, UUIDId)
    return EntityReference(kind=kind, id=id_type.parse(identifier))


def contact_to_model(contact: Contact, model: ContactModel | None = None) -> ContactModel:
    target = model or ContactModel(
        id=str(contact.id),
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )
    target.first_name = contact.first_name
    target.last_name = contact.last_name
    target.display_name = contact.display_name
    target.status = contact.status.value
    target.owner_id = str(contact.owner_id) if contact.owner_id is not None else None
    target.source = contact.source
    target.metadata_json = dict(contact.metadata)
    target.archived_at = contact.archived_at
    target.created_at = contact.created_at
    target.updated_at = contact.updated_at
    return target


def contact_from_model(
    model: ContactModel,
    emails: list[ContactEmailModel],
    phones: list[ContactPhoneModel],
    addresses: list[ContactAddressModel],
) -> Contact:
    return Contact(
        id=ContactId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        first_name=model.first_name,
        last_name=model.last_name,
        display_name=model.display_name,
        status=ContactStatus(model.status),
        owner_id=EntityId.parse(model.owner_id) if model.owner_id is not None else None,
        source=model.source,
        emails=tuple(
            ContactEmail(
                row.value,
                is_primary=row.is_primary,
                verification=VerificationState(row.verification),
            )
            for row in sorted(emails, key=lambda item: item.position)
        ),
        phones=tuple(
            ContactPhone(
                row.value,
                is_primary=row.is_primary,
                verification=VerificationState(row.verification),
            )
            for row in sorted(phones, key=lambda item: item.position)
        ),
        addresses=tuple(
            Address(
                line1=row.line1,
                city=row.city,
                postal_code=row.postal_code,
                line2=row.line2,
                region=row.region,
                country_code=row.country_code,
                is_primary=row.is_primary,
            )
            for row in sorted(addresses, key=lambda item: item.position)
        ),
        metadata=dict(model.metadata_json or {}),
        archived_at=aware(model.archived_at),
    )


def organization_to_model(
    organization: Organization,
    model: OrganizationModel | None = None,
) -> OrganizationModel:
    target = model or OrganizationModel(
        id=str(organization.id),
        created_at=organization.created_at,
        updated_at=organization.updated_at,
    )
    target.legal_name = organization.legal_name
    target.trading_name = organization.trading_name
    target.display_name = organization.display_name
    target.registration_number = organization.registration_number
    target.tax_id = organization.tax_id
    target.status = organization.status.value
    target.owner_id = str(organization.owner_id) if organization.owner_id is not None else None
    target.source = organization.source
    target.metadata_json = dict(organization.metadata)
    target.archived_at = organization.archived_at
    target.created_at = organization.created_at
    target.updated_at = organization.updated_at
    return target


def organization_from_model(
    model: OrganizationModel,
    domains: list[OrganizationDomainModel],
    addresses: list[OrganizationAddressModel],
) -> Organization:
    return Organization(
        id=OrganizationId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        legal_name=model.legal_name,
        trading_name=model.trading_name,
        display_name=model.display_name,
        registration_number=model.registration_number,
        tax_id=model.tax_id,
        status=OrganizationStatus(model.status),
        owner_id=EntityId.parse(model.owner_id) if model.owner_id is not None else None,
        source=model.source,
        domains=tuple(
            OrganizationDomain(row.value, is_primary=row.is_primary)
            for row in sorted(domains, key=lambda item: item.position)
        ),
        addresses=tuple(
            OrganizationAddress(
                line1=row.line1,
                city=row.city,
                postal_code=row.postal_code,
                line2=row.line2,
                region=row.region,
                country_code=row.country_code,
                is_primary=row.is_primary,
            )
            for row in sorted(addresses, key=lambda item: item.position)
        ),
        metadata=dict(model.metadata_json or {}),
        archived_at=aware(model.archived_at),
    )


def relationship_endpoint(kind: str, identifier: str) -> RelationshipEndpoint:
    parsed_kind = RelationshipEntityKind(kind)
    if parsed_kind is RelationshipEntityKind.CONTACT:
        return RelationshipEndpoint.contact(ContactId.parse(identifier))
    return RelationshipEndpoint.organization(OrganizationId.parse(identifier))


def relationship_to_model(
    relationship: Relationship,
    model: RelationshipModel | None = None,
) -> RelationshipModel:
    target = model or RelationshipModel(
        id=str(relationship.id),
        created_at=relationship.created_at,
        updated_at=relationship.updated_at,
    )
    target.source_kind = relationship.source.kind.value
    target.source_id = str(relationship.source.id)
    target.target_kind = relationship.target.kind.value
    target.target_id = str(relationship.target.id)
    target.relationship_type = relationship.relationship_type.code
    target.valid_from = relationship.valid_from
    target.role = relationship.role
    target.title = relationship.title
    target.is_primary = relationship.is_primary
    target.valid_until = relationship.valid_until
    target.metadata_json = dict(relationship.metadata)
    target.created_at = relationship.created_at
    target.updated_at = relationship.updated_at
    return target


def relationship_from_model(model: RelationshipModel) -> Relationship:
    return Relationship(
        id=RelationshipId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        source=relationship_endpoint(model.source_kind, model.source_id),
        target=relationship_endpoint(model.target_kind, model.target_id),
        relationship_type=RelationshipType(model.relationship_type),
        valid_from=aware(model.valid_from),
        role=model.role,
        title=model.title,
        is_primary=model.is_primary,
        valid_until=aware(model.valid_until),
        metadata=dict(model.metadata_json or {}),
    )


def tag_to_model(tag: Tag, model: TagModel | None = None) -> TagModel:
    target = model or TagModel(
        id=str(tag.id),
        created_at=tag.created_at,
        updated_at=tag.updated_at,
    )
    target.name = tag.name.value
    target.normalized_name = tag.name.normalized
    target.metadata_json = dict(tag.metadata)
    target.created_at = tag.created_at
    target.updated_at = tag.updated_at
    return target


def tag_from_model(model: TagModel) -> Tag:
    return Tag(
        id=TagId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        name=TagName(model.name),
        metadata=dict(model.metadata_json or {}),
    )


def tag_assignment_to_model(assignment: TagAssignment) -> TagAssignmentModel:
    return TagAssignmentModel(
        id=str(assignment.id),
        tag_id=str(assignment.tag_id),
        entity_kind=assignment.entity.kind,
        entity_id=str(assignment.entity.id),
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def tag_assignment_from_model(model: TagAssignmentModel) -> TagAssignment:
    return TagAssignment(
        id=TagAssignmentId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        tag_id=TagId.parse(model.tag_id),
        entity=entity_reference(model.entity_kind, model.entity_id),
    )


def custom_field_definition_to_model(
    definition: CustomFieldDefinition,
) -> CustomFieldDefinitionModel:
    return CustomFieldDefinitionModel(
        id=str(definition.id),
        key=definition.key,
        label=definition.label,
        field_type=definition.field_type.value,
        schema_version=definition.schema_version,
        applies_to_json=list(definition.applies_to),
        required=definition.required,
        description=definition.description,
        options_json=[
            {"code": option.code, "label": option.label}
            for option in definition.options
        ],
        reference_kinds_json=list(definition.reference_kinds),
        active=definition.active,
        metadata_json=dict(definition.metadata),
        created_at=definition.created_at,
        updated_at=definition.updated_at,
    )


def custom_field_definition_from_model(
    model: CustomFieldDefinitionModel,
) -> CustomFieldDefinition:
    return CustomFieldDefinition(
        id=CustomFieldDefinitionId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        key=model.key,
        label=model.label,
        field_type=CustomFieldType(model.field_type),
        schema_version=model.schema_version,
        applies_to=tuple(model.applies_to_json or []),
        required=model.required,
        description=model.description,
        options=tuple(
            CustomFieldOption(**item) for item in (model.options_json or [])
        ),
        reference_kinds=tuple(model.reference_kinds_json or []),
        active=model.active,
        metadata=dict(model.metadata_json or {}),
    )


def encode_custom_value(value: object) -> dict[str, object]:
    """Encode Custom Field Python values into a JSON-safe tagged envelope."""
    if value is None:
        return {"type": "none", "value": None}
    if isinstance(value, EntityReference):
        return {
            "type": "reference",
            "value": {"kind": value.kind, "id": str(value.id)},
        }
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if type(value) is date:
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, tuple):
        return {"type": "tuple", "value": list(value)}
    if type(value) is bool:
        return {"type": "bool", "value": value}
    if type(value) is int:
        return {"type": "int", "value": value}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, list):
        return {"type": "list", "value": value}
    if isinstance(value, dict):
        return {"type": "dict", "value": value}
    raise TypeError(
        f"Unsupported Custom Field persistence value: {type(value).__name__}"
    )


def decode_custom_value(payload: object) -> object:
    """Decode a tagged Custom Field value produced by encode_custom_value."""
    if not isinstance(payload, dict) or "type" not in payload:
        return payload
    kind = payload.get("type")
    value = payload.get("value")
    if kind == "none":
        return None
    if kind == "reference" and isinstance(value, dict):
        return entity_reference(str(value["kind"]), str(value["id"]))
    if kind == "decimal":
        return Decimal(str(value))
    if kind == "datetime":
        return datetime.fromisoformat(str(value))
    if kind == "date":
        return date.fromisoformat(str(value))
    if kind == "tuple":
        return tuple(value if isinstance(value, list) else ())
    return value


def custom_field_value_to_model(
    value: CustomFieldValue,
    model: CustomFieldValueModel | None = None,
) -> CustomFieldValueModel:
    target = model or CustomFieldValueModel(
        id=str(value.id),
        created_at=value.created_at,
        updated_at=value.updated_at,
    )
    target.definition_id = str(value.definition_id)
    target.entity_kind = value.entity.kind
    target.entity_id = str(value.entity.id)
    target.schema_version = value.schema_version
    target.value_json = encode_custom_value(value.value)
    target.created_at = value.created_at
    target.updated_at = value.updated_at
    return target


def custom_field_value_from_model(model: CustomFieldValueModel) -> CustomFieldValue:
    return CustomFieldValue(
        id=CustomFieldValueId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        definition_id=CustomFieldDefinitionId.parse(model.definition_id),
        entity=entity_reference(model.entity_kind, model.entity_id),
        schema_version=model.schema_version,
        value=decode_custom_value(model.value_json),
    )


def activity_to_model(
    activity: Activity,
    model: ActivityModel | None = None,
) -> ActivityModel:
    target = model or ActivityModel(
        id=str(activity.id),
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )
    target.type = activity.type.value
    target.occurred_at = activity.occurred_at
    target.subject = activity.subject
    target.description = activity.description
    target.direction = (
        activity.direction.value if activity.direction is not None else None
    )
    target.duration_seconds = activity.duration_seconds
    target.source = activity.source
    target.external_id = activity.external_id
    target.metadata_json = dict(activity.metadata)
    target.created_at = activity.created_at
    target.updated_at = activity.updated_at
    return target


def activity_from_model(
    model: ActivityModel,
    participants: list[ActivityParticipantModel],
    references: list[ActivityReferenceModel],
) -> Activity:
    return Activity(
        id=ActivityId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        type=ActivityType(model.type),
        occurred_at=aware(model.occurred_at),
        subject=model.subject,
        description=model.description,
        direction=(
            ActivityDirection(model.direction)
            if model.direction is not None
            else None
        ),
        duration_seconds=model.duration_seconds,
        participants=tuple(
            ActivityParticipant(
                reference=entity_reference(row.entity_kind, row.entity_id),
                role=row.role,
                is_primary=row.is_primary,
            )
            for row in sorted(participants, key=lambda item: item.position)
        ),
        references=tuple(
            entity_reference(row.entity_kind, row.entity_id)
            for row in sorted(references, key=lambda item: item.position)
        ),
        source=model.source,
        external_id=model.external_id,
        metadata=dict(model.metadata_json or {}),
    )


def task_to_model(task: Task, model: TaskModel | None = None) -> TaskModel:
    target = model or TaskModel(
        id=str(task.id),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
    target.title = task.title
    target.status = task.status.value
    target.priority = int(task.priority)
    target.description = task.description
    target.due_at = task.due_at
    target.owner_id = task.owner_id
    target.assignee_id = task.assignee_id
    target.source = task.source
    target.external_id = task.external_id
    target.metadata_json = dict(task.metadata)
    target.started_at = task.started_at
    target.completed_at = task.completed_at
    target.cancelled_at = task.cancelled_at
    target.created_at = task.created_at
    target.updated_at = task.updated_at
    return target


def task_from_model(
    model: TaskModel,
    references: list[TaskReferenceModel],
) -> Task:
    return Task(
        id=TaskId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        title=model.title,
        status=TaskStatus(model.status),
        priority=TaskPriority(model.priority),
        description=model.description,
        due_at=aware(model.due_at),
        owner_id=model.owner_id,
        assignee_id=model.assignee_id,
        references=tuple(
            entity_reference(row.entity_kind, row.entity_id)
            for row in sorted(references, key=lambda item: item.position)
        ),
        source=model.source,
        external_id=model.external_id,
        metadata=dict(model.metadata_json or {}),
        started_at=aware(model.started_at),
        completed_at=aware(model.completed_at),
        cancelled_at=aware(model.cancelled_at),
    )


def lead_to_model(lead: Lead, model: LeadModel | None = None) -> LeadModel:
    target = model or LeadModel(
        id=str(lead.id),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )
    target.contact_id = str(lead.contact_id)
    target.organization_id = (
        str(lead.organization_id) if lead.organization_id is not None else None
    )
    target.source = lead.source
    target.status = lead.status.value
    target.converted_opportunity_id = (
        str(lead.converted_opportunity_id)
        if lead.converted_opportunity_id is not None
        else None
    )
    target.conversion_idempotency_key = lead.conversion_idempotency_key
    target.conversion_request_fingerprint = lead.conversion_request_fingerprint
    target.created_at = lead.created_at
    target.updated_at = lead.updated_at
    return target


def lead_from_model(model: LeadModel) -> Lead:
    return Lead(
        id=LeadId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        contact_id=ContactId.parse(model.contact_id),
        organization_id=(
            OrganizationId.parse(model.organization_id)
            if model.organization_id
            else None
        ),
        source=model.source,
        status=LeadStatus(model.status),
        converted_opportunity_id=(
            OpportunityId.parse(model.converted_opportunity_id)
            if model.converted_opportunity_id is not None
            else None
        ),
        conversion_idempotency_key=model.conversion_idempotency_key,
        conversion_request_fingerprint=model.conversion_request_fingerprint,
    )


def opportunity_to_model(
    opportunity: Opportunity,
    model: OpportunityModel | None = None,
) -> OpportunityModel:
    target = model or OpportunityModel(
        id=str(opportunity.id),
        created_at=opportunity.created_at,
        updated_at=opportunity.updated_at,
    )
    target.name = opportunity.name
    target.contact_id = str(opportunity.contact_id)
    target.organization_id = (
        str(opportunity.organization_id)
        if opportunity.organization_id is not None
        else None
    )
    target.pipeline_id = opportunity.pipeline_id
    target.stage_id = opportunity.stage_id
    target.stage_entered_at = opportunity.stage_entered_at
    target.estimated_value = opportunity.estimated_value
    target.currency = opportunity.currency
    target.probability = opportunity.probability
    target.expected_close_date = opportunity.expected_close_date
    target.owner_id = opportunity.owner_id
    target.status = opportunity.status.value
    target.created_at = opportunity.created_at
    target.updated_at = opportunity.updated_at
    return target


def opportunity_from_model(model: OpportunityModel) -> Opportunity:
    return Opportunity(
        id=OpportunityId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        name=model.name,
        contact_id=ContactId.parse(model.contact_id),
        organization_id=(
            OrganizationId.parse(model.organization_id)
            if model.organization_id
            else None
        ),
        pipeline_id=model.pipeline_id,
        stage_id=model.stage_id,
        stage_entered_at=aware(model.stage_entered_at),
        estimated_value=model.estimated_value,
        currency=model.currency,
        probability=model.probability,
        expected_close_date=model.expected_close_date,
        owner_id=model.owner_id,
        status=OpportunityStatus(model.status),
    )


def pipeline_from_models(
    pipeline: PipelineModel,
    stages: list[PipelineStageModel],
    transitions: list[PipelineTransitionModel],
) -> Pipeline:
    return Pipeline(
        id=pipeline.id,
        name=pipeline.name,
        stages=tuple(
            Stage(
                id=row.id,
                name=row.name,
                position=row.position,
                default_probability=row.default_probability,
                terminal=row.terminal,
                outcome=(
                    StageOutcome(row.outcome)
                    if row.outcome is not None
                    else None
                ),
            )
            for row in sorted(stages, key=lambda item: (item.position, item.id))
        ),
        transitions=tuple(
            StageTransition(row.from_stage, row.to_stage)
            for row in sorted(
                transitions,
                key=lambda item: (item.from_stage, item.to_stage),
            )
        ),
    )


def audit_to_model(entry: AuditEntry) -> AuditEntryModel:
    return AuditEntryModel(
        id=str(entry.id),
        actor_id=entry.actor_id,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        occurred_at=entry.occurred_at,
        changes_json=dict(entry.changes),
        correlation_id=entry.correlation_id,
    )


def audit_from_model(model: AuditEntryModel) -> AuditEntry:
    return AuditEntry(
        id=AuditEntryId.parse(model.id),
        actor_id=model.actor_id,
        action=model.action,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        occurred_at=aware(model.occurred_at),
        changes=dict(model.changes_json or {}),
        correlation_id=model.correlation_id,
    )


def communication_intent_to_model(
    intent: CommunicationIntent,
    model: CommunicationIntentModel | None = None,
) -> CommunicationIntentModel:
    target = model or CommunicationIntentModel(
        id=str(intent.id),
        created_at=intent.created_at,
        updated_at=intent.updated_at,
    )
    target.channel = intent.channel.value
    target.direction = intent.direction.value
    target.status = intent.status.value
    target.subject = intent.content.subject
    target.text_body = intent.content.text_body
    target.html_body = intent.content.html_body
    target.idempotency_key = intent.idempotency_key
    target.metadata_json = dict(intent.metadata)
    target.queued_at = intent.queued_at
    target.cancelled_at = intent.cancelled_at
    target.created_at = intent.created_at
    target.updated_at = intent.updated_at
    return target


def communication_intent_from_model(
    model: CommunicationIntentModel,
    recipients: list[CommunicationRecipientModel],
    references: list[CommunicationIntentReferenceModel],
) -> CommunicationIntent:
    return CommunicationIntent(
        id=CommunicationIntentId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        channel=CommunicationChannel(model.channel),
        recipients=tuple(
            CommunicationRecipient(
                address=CommunicationAddress(
                    CommunicationChannel(row.channel),
                    row.value,
                ),
                display_name=row.display_name,
                reference=(
                    entity_reference(row.reference_kind, row.reference_id)
                    if row.reference_kind is not None
                    and row.reference_id is not None
                    else None
                ),
            )
            for row in sorted(recipients, key=lambda item: item.position)
        ),
        content=CommunicationContent(
            subject=model.subject,
            text_body=model.text_body,
            html_body=model.html_body,
        ),
        direction=CommunicationDirection(model.direction),
        status=CommunicationIntentStatus(model.status),
        references=tuple(
            entity_reference(row.entity_kind, row.entity_id)
            for row in sorted(references, key=lambda item: item.position)
        ),
        idempotency_key=model.idempotency_key,
        metadata=dict(model.metadata_json or {}),
        queued_at=aware(model.queued_at),
        cancelled_at=aware(model.cancelled_at),
    )


def delivery_attempt_to_model(
    attempt: DeliveryAttempt,
    model: DeliveryAttemptModel | None = None,
) -> DeliveryAttemptModel:
    target = model or DeliveryAttemptModel(
        id=str(attempt.id),
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )
    target.intent_id = str(attempt.intent_id)
    target.attempt_number = attempt.attempt_number
    target.attempted_at = attempt.attempted_at
    target.status = attempt.status.value
    target.provider = attempt.provider
    target.provider_message_id = attempt.provider_message_id
    target.failure_code = attempt.failure_code
    target.completed_at = attempt.completed_at
    target.metadata_json = dict(attempt.metadata)
    target.created_at = attempt.created_at
    target.updated_at = attempt.updated_at
    return target


def delivery_attempt_from_model(model: DeliveryAttemptModel) -> DeliveryAttempt:
    return DeliveryAttempt(
        id=DeliveryAttemptId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        intent_id=CommunicationIntentId.parse(model.intent_id),
        attempt_number=model.attempt_number,
        attempted_at=aware(model.attempted_at),
        status=DeliveryAttemptStatus(model.status),
        provider=model.provider,
        provider_message_id=model.provider_message_id,
        failure_code=model.failure_code,
        completed_at=aware(model.completed_at),
        metadata=dict(model.metadata_json or {}),
    )


def communication_record_to_model(
    record: CommunicationRecord,
    model: CommunicationRecordModel | None = None,
) -> CommunicationRecordModel:
    target = model or CommunicationRecordModel(
        id=str(record.id),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
    target.channel = record.channel.value
    target.direction = record.direction.value
    target.occurred_at = record.occurred_at
    target.subject = record.subject
    target.intent_id = str(record.intent_id) if record.intent_id is not None else None
    target.delivery_attempt_id = (
        str(record.delivery_attempt_id)
        if record.delivery_attempt_id is not None
        else None
    )
    target.external_id = record.external_id
    target.delivery_status = (
        record.delivery_status.value if record.delivery_status else None
    )
    target.last_delivery_event_at = record.last_delivery_event_at
    target.metadata_json = dict(record.metadata)
    target.created_at = record.created_at
    target.updated_at = record.updated_at
    return target


def communication_record_from_model(
    model: CommunicationRecordModel,
    counterparties: list[CommunicationCounterpartyModel],
    references: list[CommunicationRecordReferenceModel],
) -> CommunicationRecord:
    return CommunicationRecord(
        id=CommunicationRecordId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        channel=CommunicationChannel(model.channel),
        direction=CommunicationDirection(model.direction),
        occurred_at=aware(model.occurred_at),
        counterparties=tuple(
            CommunicationAddress(
                CommunicationChannel(row.channel),
                row.value,
            )
            for row in sorted(counterparties, key=lambda item: item.position)
        ),
        subject=model.subject,
        references=tuple(
            entity_reference(row.entity_kind, row.entity_id)
            for row in sorted(references, key=lambda item: item.position)
        ),
        intent_id=(
            CommunicationIntentId.parse(model.intent_id)
            if model.intent_id
            else None
        ),
        delivery_attempt_id=(
            DeliveryAttemptId.parse(model.delivery_attempt_id)
            if model.delivery_attempt_id
            else None
        ),
        external_id=model.external_id,
        delivery_status=(
            EmailDeliveryEventType(model.delivery_status)
            if model.delivery_status
            else None
        ),
        last_delivery_event_at=aware(model.last_delivery_event_at),
        metadata=dict(model.metadata_json or {}),
    )


def email_delivery_event_to_model(
    event: EmailDeliveryEvent,
) -> EmailDeliveryEventModel:
    return EmailDeliveryEventModel(
        id=str(event.id),
        intent_id=str(event.intent_id),
        event_type=event.event_type.value,
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
        delivery_attempt_id=(
            str(event.delivery_attempt_id)
            if event.delivery_attempt_id
            else None
        ),
        provider=event.provider,
        provider_message_id=event.provider_message_id,
        external_event_id=event.external_event_id,
        recipient_channel=(
            event.recipient.channel.value if event.recipient else None
        ),
        recipient_value=event.recipient.value if event.recipient else None,
        recipient_normalized=(
            event.recipient.normalized if event.recipient else None
        ),
        failure_code=event.failure_code,
        metadata_json=dict(event.metadata),
    )


def email_delivery_event_from_model(
    model: EmailDeliveryEventModel,
) -> EmailDeliveryEvent:
    recipient = None
    if model.recipient_channel is not None and model.recipient_value is not None:
        recipient = CommunicationAddress(
            CommunicationChannel(model.recipient_channel),
            model.recipient_value,
        )
    return EmailDeliveryEvent(
        id=EmailDeliveryEventId.parse(model.id),
        intent_id=CommunicationIntentId.parse(model.intent_id),
        event_type=EmailDeliveryEventType(model.event_type),
        occurred_at=aware(model.occurred_at),
        recorded_at=aware(model.recorded_at),
        delivery_attempt_id=(
            DeliveryAttemptId.parse(model.delivery_attempt_id)
            if model.delivery_attempt_id
            else None
        ),
        provider=model.provider,
        provider_message_id=model.provider_message_id,
        external_event_id=model.external_event_id,
        recipient=recipient,
        failure_code=model.failure_code,
        metadata=dict(model.metadata_json or {}),
    )


def webhook_subscription_to_model(
    subscription: WebhookSubscription,
    model: WebhookSubscriptionModel | None = None,
) -> WebhookSubscriptionModel:
    target = model or WebhookSubscriptionModel(
        id=str(subscription.id),
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )
    target.url = subscription.url
    target.signing_secret = subscription.signing_secret
    target.disabled_at = subscription.disabled_at
    target.created_at = subscription.created_at
    target.updated_at = subscription.updated_at
    return target


def webhook_subscription_from_model(
    model: WebhookSubscriptionModel,
    events: list[WebhookSubscriptionEventModel],
) -> WebhookSubscription:
    return WebhookSubscription(
        id=WebhookSubscriptionId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        url=model.url,
        event_types=tuple(EventType.parse(row.event_type) for row in events),
        signing_secret=model.signing_secret,
        disabled_at=aware(model.disabled_at),
    )


def webhook_delivery_to_model(
    delivery: WebhookDelivery,
    model: WebhookDeliveryModel | None = None,
) -> WebhookDeliveryModel:
    target = model or WebhookDeliveryModel(
        id=str(delivery.id),
        created_at=delivery.created_at,
        updated_at=delivery.updated_at,
    )
    target.subscription_id = str(delivery.subscription_id)
    target.event_id = str(delivery.event_id)
    target.event_type = str(delivery.event_type)
    target.payload_json = delivery.payload_json
    target.idempotency_key = delivery.idempotency_key
    target.state = delivery.state.value
    target.attempt_count = delivery.attempt_count
    target.next_attempt_at = delivery.next_attempt_at
    target.last_attempt_at = delivery.last_attempt_at
    target.completed_at = delivery.completed_at
    target.last_status_code = delivery.last_status_code
    target.last_error_code = delivery.last_error_code
    target.created_at = delivery.created_at
    target.updated_at = delivery.updated_at
    return target


def webhook_delivery_from_model(
    model: WebhookDeliveryModel,
) -> WebhookDelivery:
    return WebhookDelivery(
        id=WebhookDeliveryId.parse(model.id),
        created_at=aware(model.created_at),
        updated_at=aware(model.updated_at),
        subscription_id=WebhookSubscriptionId.parse(model.subscription_id),
        event_id=EventId.parse(model.event_id),
        event_type=EventType.parse(model.event_type),
        payload_json=model.payload_json,
        idempotency_key=model.idempotency_key,
        state=WebhookDeliveryState(model.state),
        attempt_count=model.attempt_count,
        next_attempt_at=aware(model.next_attempt_at),
        last_attempt_at=aware(model.last_attempt_at),
        completed_at=aware(model.completed_at),
        last_status_code=model.last_status_code,
        last_error_code=model.last_error_code,
    )


def webhook_attempt_to_model(
    attempt: WebhookDeliveryAttempt,
) -> WebhookDeliveryAttemptModel:
    return WebhookDeliveryAttemptModel(
        delivery_id=str(attempt.delivery_id),
        attempt_number=attempt.attempt_number,
        attempted_at=attempt.attempted_at,
        outcome=attempt.outcome.value,
        status_code=attempt.status_code,
        error_code=attempt.error_code,
        next_attempt_at=attempt.next_attempt_at,
    )


def webhook_attempt_from_model(
    model: WebhookDeliveryAttemptModel,
) -> WebhookDeliveryAttempt:
    return WebhookDeliveryAttempt(
        delivery_id=WebhookDeliveryId.parse(model.delivery_id),
        attempt_number=model.attempt_number,
        attempted_at=aware(model.attempted_at),
        outcome=WebhookDeliveryAttemptOutcome(model.outcome),
        status_code=model.status_code,
        error_code=model.error_code,
        next_attempt_at=aware(model.next_attempt_at),
    )


def timeline_to_model(entry: TimelineEntry) -> TimelineEntryModel:
    return TimelineEntryModel(
        id=str(entry.id),
        kind=entry.kind.value,
        event_type=str(entry.event_type),
        source_event_id=str(entry.source_event_id),
        entity_kind=entry.entity.kind,
        entity_id=str(entry.entity.id),
        entity_id_type=type(entry.entity.id).__name__,
        occurred_at=entry.occurred_at,
        title=entry.title,
        summary=entry.summary,
        actor_id=entry.actor_id,
        correlation_id=entry.correlation_id,
        metadata_json=dict(entry.metadata),
    )


def timeline_from_model(
    model: TimelineEntryModel,
    references: list[TimelineReferenceModel],
) -> TimelineEntry:
    return TimelineEntry(
        id=TimelineEntryId.parse(model.id),
        kind=TimelineEntryKind(model.kind),
        event_type=EventType.parse(model.event_type),
        source_event_id=EventId.parse(model.source_event_id),
        entity=entity_reference(
            model.entity_kind,
            model.entity_id,
            model.entity_id_type,
        ),
        occurred_at=aware(model.occurred_at),
        title=model.title,
        summary=model.summary,
        references=tuple(
            entity_reference(
                row.entity_kind,
                row.entity_id,
                row.entity_id_type,
            )
            for row in sorted(references, key=lambda item: item.position)
        ),
        actor_id=model.actor_id,
        correlation_id=model.correlation_id,
        metadata=dict(model.metadata_json or {}),
    )


def json_value(value: Any) -> Any:
    """Marker helper kept for adapters that need an explicit JSON persistence boundary."""
    return value
