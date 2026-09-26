"""SQLAlchemy repository adapters for PyCRMKit domain contracts."""

from pycrmkit.storage.sqlalchemy.repositories.activities import (
    SQLAlchemyActivityRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.audit import (
    SQLAlchemyAuditRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.communication import (
    SQLAlchemyCommunicationRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.contacts import (
    SQLAlchemyContactRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.custom_fields import (
    SQLAlchemyCustomFieldRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.external_identities import (
    SQLAlchemyExternalIdentityRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.leads import (
    SQLAlchemyLeadRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.opportunities import (
    SQLAlchemyOpportunityRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.organizations import (
    SQLAlchemyOrganizationRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.pipelines import (
    SQLAlchemyPipelineRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.relationships import (
    SQLAlchemyRelationshipRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.tags import (
    SQLAlchemyTagRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.tasks import (
    SQLAlchemyTaskRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.timeline import (
    SQLAlchemyTimelineRepository,
)
from pycrmkit.storage.sqlalchemy.repositories.webhooks import (
    SQLAlchemyWebhookDeliveryRepository,
    SQLAlchemyWebhookSubscriptionRepository,
)

__all__ = [
    "SQLAlchemyActivityRepository",
    "SQLAlchemyAuditRepository",
    "SQLAlchemyCommunicationRepository",
    "SQLAlchemyContactRepository",
    "SQLAlchemyCustomFieldRepository",
    "SQLAlchemyExternalIdentityRepository",
    "SQLAlchemyLeadRepository",
    "SQLAlchemyOpportunityRepository",
    "SQLAlchemyOrganizationRepository",
    "SQLAlchemyPipelineRepository",
    "SQLAlchemyRelationshipRepository",
    "SQLAlchemyTagRepository",
    "SQLAlchemyTaskRepository",
    "SQLAlchemyTimelineRepository",
    "SQLAlchemyWebhookDeliveryRepository",
    "SQLAlchemyWebhookSubscriptionRepository",
]
