"""LOT-31-014: opt-in FastAPI reference host with explicit tenant security.

This is a host-owned reference application, not PyCRMKit's built-in IAM.
Only Campaign routes are mounted. Generic CRM endpoints would otherwise lack
this host's tenant policy; those MUST NOT be published by this example.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import io
import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from pycrmkit import CRM
from pycrmkit.campaigns import CampaignId, export_campaign_records, import_campaign_members
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.events import InProcessEventBus
from pycrmkit.importers import IterableReader
from pycrmkit.integrations.campaign_security import CampaignPrincipal, CampaignSecurityBoundary
from pycrmkit.integrations.fastapi import install_error_handlers
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.integrations.fastapi.routers.campaigns import create_campaigns_router
from pycrmkit.segments import SegmentId
from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork
from pycrmkit.storage.sqlalchemy.models.campaign import CampaignModel

_ISSUER = "pycrmkit-rc1-host-fixture"
_AUDIENCE = "pycrmkit-campaign-host"
_TENANT = re.compile(r"^[a-z][a-z0-9_-]{0,35}$")
_SUBJECT = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")
_ALLOWED_READ = {
    "campaign.read", "campaign.members.read", "campaign.sources.read",
    "campaign.attribution.read", "campaign.lifecycle",
}
_ALLOWED_HOST = {
    "host.campaign.create", "host.campaign.capture", "host.campaign.import",
    "host.campaign.export", "host.campaign.attribution",
    "host.campaign.communication",
}


def _owner(tenant: str) -> EntityId:
    """Deterministic owner for this test host. Real hosts map trusted IAM IDs."""
    return EntityId(uuid5(NAMESPACE_URL, "pycrmkit-rc1-host:" + tenant))


def _b64_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verified_claims(request: Request, signing_key: bytes) -> dict[str, object] | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    parts = token.split(".")
    if len(parts) != 2 or any(len(part) > 1024 for part in parts):
        return None
    try:
        raw, supplied_mac = map(_b64_decode, parts)
        expected = hmac.digest(signing_key, raw, hashlib.sha256)
        if not hmac.compare_digest(supplied_mac, expected):
            return None
        claims = json.loads(raw.decode("utf-8"))
        if not isinstance(claims, dict):
            return None
        tenant, sub = claims.get("tenant"), claims.get("sub")
        now = int(time.time())
        issued, expires = claims.get("iat"), claims.get("exp")
        if (
            not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
            or not isinstance(sub, str) or not _SUBJECT.fullmatch(sub)
            or claims.get("iss") != _ISSUER
            or claims.get("aud") != _AUDIENCE
            or claims.get("role") != "campaign_admin"
            or type(issued) is not int or type(expires) is not int
            or issued > now + 30 or issued < now - 3600
            or expires <= now or expires > issued + 900
        ):
            return None
        return claims
    except (ValueError, UnicodeError, OverflowError, binascii.Error):
        return None


def _tenant_from(principal: CampaignPrincipal) -> str:
    return principal.actor_id.split(":", 2)[1]


class HostCreateCampaign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)


class HostImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_kind: Literal["contact"]
    entity_id: UUID


class HostImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[HostImportRow] = Field(min_length=1, max_length=1000)


class HostAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: UUID
    source: str = Field(min_length=1, max_length=120)


@dataclass(slots=True)
class HostResources:
    engine: object
    sessions: object
    event_bus: InProcessEventBus
    crm: CRM
    factory_calls: int = 0

    def uow(self) -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(self.sessions, event_publisher=self.event_bus)


def create_app(database_url: str | None = None, signing_secret: str | None = None) -> FastAPI:
    """Require migrations and host secret before accepting any request."""
    url = database_url or os.environ.get("PYCRMKIT_DATABASE_URL", "")
    secret = signing_secret or os.environ.get("PYCRMKIT_RC_HOST_SIGNING_KEY", "")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("RC host requires a migrated PostgreSQL psycopg database")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("RC host requires externally configured >=32-byte signing key")

    engine = create_engine(url, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    bus = InProcessEventBus()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(sessions, event_publisher=bus)

    resources = HostResources(
        engine=engine,
        sessions=sessions,
        event_bus=bus,
        crm=CRM(
            uow_factory=uow_factory, event_bus=bus,
            webhook_auto_delivery=False,
        ),
    )

    def principal(request: object) -> CampaignPrincipal | None:
        if not isinstance(request, Request):
            return None
        claims = _verified_claims(request, secret.encode("utf-8"))
        if claims is None:
            return None
        return CampaignPrincipal(f"host:{claims['tenant']}:{claims['sub']}")

    def authorized(
        identity: CampaignPrincipal, *, action: str,
        campaign_id: str | None, scope: Mapping[str, object] | None,
    ) -> bool:
        tenant = _tenant_from(identity)
        owner_id = str(_owner(tenant))
        if action == "campaign.list":
            return bool(
                campaign_id is None and scope is not None
                and scope.get("owner_id") == owner_id
                and scope.get("include_archived") is False
            )
        if action == "host.campaign.create":
            return campaign_id is None
        if action not in _ALLOWED_READ | _ALLOWED_HOST or campaign_id is None:
            # No generic Campaign create/update/member writes/source writes/
            # attribution writes/communication links, which cannot enforce
            # tenant ownership for all referenced entities.
            return False
        try:
            UUID(campaign_id)
        except ValueError:
            return False
        # Host-specific ownership check occurs BEFORE the CRM factory is used.
        # This check uses the SQL database but no Campaign facade/repository.
        with engine.connect() as connection:
            stored = connection.execute(
                select(CampaignModel.owner_id).where(
                    CampaignModel.id == campaign_id
                )
            ).scalar_one_or_none()
        return stored is not None and stored == owner_id

    security = CampaignSecurityBoundary(principal, authorized)

    def crm_factory() -> CRM:
        resources.factory_calls += 1
        return resources.crm

    access = CampaignHTTPAccess(crm_factory, security)
    app = FastAPI(title="PyCRMKit RC1 Tenant-Secured Host Reference")
    install_error_handlers(app)
    # Not create_crm_router: that would expose unrestricted Contacts/Segments.
    app.include_router(create_campaigns_router(access), prefix="/crm")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/host/campaigns", status_code=201)
    def create(payload: HostCreateCampaign, request: Request) -> dict[str, object]:
        crm = access.crm_for(request, action="host.campaign.create")
        identity = principal(request)
        assert identity is not None
        campaign = crm.campaigns.create(
            key=payload.key, name=payload.name,
            owner_id=_owner(_tenant_from(identity)),
        )
        return {
            "id": str(campaign.id), "revision": campaign.revision,
            "owner_id": str(campaign.owner_id),
        }

    @app.post("/host/campaigns/{campaign_id}/capture/{segment_id}", status_code=201)
    def capture(campaign_id: UUID, segment_id: UUID, request: Request) -> dict[str, int]:
        crm = access.crm_for(
            request, action="host.campaign.capture", campaign_id=str(campaign_id),
        )
        identity = principal(request)
        assert identity is not None
        segment = crm.segments.get(SegmentId(segment_id))
        owner = _owner(_tenant_from(identity))
        if segment.owner_id != owner or segment.entity_kind != "contact":
            raise HTTPException(status_code=403, detail="Campaign access denied")
        # Ownership of the Segment definition is NOT sufficient: captured
        # members must also belong to the tenant before any snapshot write.
        offset = 0
        while True:
            members = crm.segments.evaluate(
                SegmentId(segment_id), OffsetPageRequest(limit=200, offset=offset),
            )
            if members.total > 1000:
                raise HTTPException(status_code=413, detail="Capture limit exceeded")
            for member in members.items:
                if member.kind != "contact" or (
                    crm.contacts.get(member.id).owner_id != owner
                ):
                    raise HTTPException(status_code=403, detail="Campaign access denied")
            if not members.has_next:
                break
            offset += len(members.items)
            if not members.items:
                raise RuntimeError("Invalid Segment pagination")
        source = crm.campaigns.attach_segment_source(
            CampaignId(campaign_id), SegmentId(segment_id),
        )
        return {"member_count": source.member_count}

    @app.post("/host/campaigns/{campaign_id}/import")
    def import_members(
        campaign_id: UUID, payload: HostImport, request: Request,
    ) -> dict[str, int]:
        crm = access.crm_for(
            request, action="host.campaign.import", campaign_id=str(campaign_id),
        )
        identity = principal(request)
        assert identity is not None
        tenant_owner = _owner(_tenant_from(identity))
        for row in payload.rows:
            contact = crm.contacts.get(ContactId(row.entity_id))
            if contact.owner_id != tenant_owner:
                raise HTTPException(status_code=403, detail="Campaign access denied")
        report = import_campaign_members(
            crm.campaigns, CampaignId(campaign_id),
            IterableReader(
                {"entity_kind": row.entity_kind, "entity_id": str(row.entity_id)}
                for row in payload.rows
            ),
            retain_row_results=False,
        )
        return report.as_dict()

    @app.get("/host/campaigns/{campaign_id}/export")
    def export(campaign_id: UUID, request: Request) -> Response:
        crm = access.crm_for(
            request, action="host.campaign.export", campaign_id=str(campaign_id),
        )
        # Deliberately bounded reference response. Real hosts should stream
        # a destination from export_campaign_records for large exports.
        if crm.campaigns.audience_count(CampaignId(campaign_id)) > 1000:
            raise HTTPException(status_code=413, detail="Export limit exceeded")
        sink = io.StringIO()
        export_campaign_records(
            crm.campaigns, CampaignId(campaign_id), sink,
            kind="audience", format="jsonl", page_size=100,
        )
        return Response(content=sink.getvalue(), media_type="application/x-ndjson")

    @app.post("/host/campaigns/{campaign_id}/attribution", status_code=201)
    def attribution(
        campaign_id: UUID, payload: HostAttribution, request: Request,
    ) -> dict[str, str]:
        crm = access.crm_for(
            request, action="host.campaign.attribution", campaign_id=str(campaign_id),
        )
        identity = principal(request)
        assert identity is not None
        contact = crm.contacts.get(ContactId(payload.contact_id))
        if contact.owner_id != _owner(_tenant_from(identity)):
            raise HTTPException(status_code=403, detail="Campaign access denied")
        result = crm.campaigns.add_attribution(
            CampaignId(campaign_id),
            EntityReference("contact", contact.id), source=payload.source,
        )
        return {"source": result.source}

    @app.post("/host/campaigns/{campaign_id}/communication/{communication_id}", status_code=201)
    def link_communication(
        campaign_id: UUID, communication_id: UUID, request: Request,
    ) -> dict[str, str]:
        crm = access.crm_for(
            request, action="host.campaign.communication", campaign_id=str(campaign_id),
        )
        identity = principal(request)
        assert identity is not None
        with resources.uow() as uow:
            record = uow.communications.get_record(CommunicationRecordId(communication_id))
            # Simulated external host-owned tenant association. Do NOT regard
            # arbitrary record metadata as trustworthy in a real IAM system.
            if record.metadata.get("tenant") != _tenant_from(identity):
                raise HTTPException(status_code=403, detail="Campaign access denied")
        link = crm.campaigns.link_communication(
            CampaignId(campaign_id), CommunicationRecordId(communication_id),
        )
        return {"communication_id": str(link.communication_id), "role": link.role}

    app.state.pycrmkit_host = resources
    return app
