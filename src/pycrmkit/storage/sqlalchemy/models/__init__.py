"""Declarative persistence models for the SQLAlchemy adapter."""

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
from pycrmkit.storage.sqlalchemy.models.timeline import (
    TimelineEntryModel,
    TimelineReferenceModel,
)
from pycrmkit.storage.sqlalchemy.models.webhook import (
    WebhookDeliveryAttemptModel,
    WebhookDeliveryModel,
    WebhookSubscriptionEventModel,
    WebhookSubscriptionModel,
)

__all__ = [
    "ActivityModel",
    "ActivityParticipantModel",
    "ActivityReferenceModel",
    "AuditEntryModel",
    "CommunicationCounterpartyModel",
    "CommunicationIntentModel",
    "CommunicationIntentReferenceModel",
    "CommunicationRecipientModel",
    "CommunicationRecordModel",
    "CommunicationRecordReferenceModel",
    "ContactAddressModel",
    "ContactEmailModel",
    "ContactModel",
    "ContactPhoneModel",
    "CustomFieldDefinitionModel",
    "CustomFieldValueModel",
    "DeliveryAttemptModel",
    "EmailDeliveryEventModel",
    "LeadModel",
    "OpportunityModel",
    "OrganizationAddressModel",
    "OrganizationDomainModel",
    "OrganizationModel",
    "PipelineModel",
    "PipelineStageModel",
    "PipelineTransitionModel",
    "RelationshipModel",
    "TagAssignmentModel",
    "TagModel",
    "TaskModel",
    "TaskReferenceModel",
    "TimelineEntryModel",
    "TimelineReferenceModel",
    "WebhookDeliveryAttemptModel",
    "WebhookDeliveryModel",
    "WebhookSubscriptionEventModel",
    "WebhookSubscriptionModel",
]
