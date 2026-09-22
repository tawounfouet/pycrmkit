"""Transactional Lead-to-Opportunity conversion workflow."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pycrmkit.core.ids import IDFactory
from pycrmkit.core.time import Clock
from pycrmkit.exceptions import ConflictError, InvalidStateError, ValidationError
from pycrmkit.leads.entities import Lead, LeadId, LeadStatus
from pycrmkit.leads.repository import LeadRepository
from pycrmkit.opportunities import Opportunity, OpportunityRepository, OpportunityService
from pycrmkit.pipelines import PipelineRepository


@dataclass(frozen=True, slots=True)
class LeadConversionResult:
    """Result of a conversion command, including whether new state was created."""

    lead: Lead
    opportunity: Opportunity
    created: bool


@dataclass(slots=True)
class LeadConversionService:
    """Atomic-ready workflow spanning Lead and Opportunity repositories.

    The caller owns the outer Unit of Work. Repositories passed to this service
    must therefore participate in the same transaction.
    """

    leads: LeadRepository
    opportunities: OpportunityRepository
    id_factory: IDFactory
    clock: Clock
    pipelines: PipelineRepository | None = None

    def convert(
        self,
        lead_id: LeadId,
        *,
        name: str | None = None,
        estimated_value: Decimal | None = None,
        currency: str | None = None,
        pipeline_id: str | None = None,
        expected_close_date: date | None = None,
        owner_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> LeadConversionResult:
        """Convert a qualified Lead exactly once at the domain workflow level."""

        lead = self.leads.get(lead_id)
        effective_name = _effective_name(name, lead)
        key = _normalize_idempotency_key(idempotency_key, lead.id)
        fingerprint = _request_fingerprint(
            lead_id=lead.id,
            name=effective_name,
            estimated_value=estimated_value,
            currency=currency,
            pipeline_id=pipeline_id,
            expected_close_date=expected_close_date,
            owner_id=owner_id,
        )

        if lead.status is LeadStatus.CONVERTED:
            return self._resolve_retry(
                lead,
                idempotency_key=key,
                request_fingerprint=fingerprint,
            )
        if lead.status is not LeadStatus.QUALIFIED:
            raise InvalidStateError(
                "lead must be qualified before conversion",
                code="lead.conversion.requires_qualified",
                context={
                    "lead_id": str(lead.id),
                    "status": lead.status.value,
                },
            )

        stage_id: str | None = None
        probability: Decimal | None = None
        pipeline = None
        if pipeline_id is not None:
            if self.pipelines is None:
                raise InvalidStateError(
                    "pipeline repository is required for lead conversion",
                    code="lead.conversion.pipeline.repository_required",
                )
            pipeline = self.pipelines.get(pipeline_id)
            stage_id = pipeline.initial_stage.id
            probability = pipeline.initial_stage.default_probability
            pipeline_id = pipeline.id

        service = OpportunityService(
            self.opportunities,
            id_factory=self.id_factory,
            clock=self.clock,
            pipeline_repository=self.pipelines,
        )
        opportunity = service.create(
            name=effective_name,
            contact_id=lead.contact_id,
            organization_id=lead.organization_id,
            pipeline_id=pipeline_id,
            stage_id=stage_id,
            estimated_value=estimated_value,
            currency=currency,
            probability=probability,
            expected_close_date=expected_close_date,
            owner_id=owner_id,
        )

        if pipeline is not None and pipeline.initial_stage.terminal:
            outcome = pipeline.initial_stage.outcome
            assert outcome is not None
            value = str(outcome)
            if value == "won":
                opportunity = service.mark_won(opportunity.id)
            elif value == "lost":
                opportunity = service.mark_lost(opportunity.id)
            elif value == "cancelled":
                opportunity = service.cancel(opportunity.id)
            else:  # pragma: no cover - Stage validation makes this exhaustive.
                raise AssertionError(f"unsupported pipeline outcome: {value}")

        lead.mark_converted(
            self.clock.now(),
            opportunity_id=opportunity.id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
        )
        self.leads.save(lead)
        return LeadConversionResult(
            lead=lead,
            opportunity=opportunity,
            created=True,
        )

    def _resolve_retry(
        self,
        lead: Lead,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> LeadConversionResult:
        opportunity_id = lead.converted_opportunity_id
        stored_key = lead.conversion_idempotency_key
        stored_fingerprint = lead.conversion_request_fingerprint
        if opportunity_id is None or stored_key is None or stored_fingerprint is None:
            raise InvalidStateError(
                "lead is already converted without replayable conversion provenance",
                code="lead.conversion.already_converted",
                context={"lead_id": str(lead.id)},
            )
        if stored_key != idempotency_key:
            raise InvalidStateError(
                "lead has already been converted",
                code="lead.conversion.already_converted",
                context={
                    "lead_id": str(lead.id),
                    "opportunity_id": str(opportunity_id),
                },
            )
        if stored_fingerprint != request_fingerprint:
            raise ConflictError(
                "idempotency key was already used with a different conversion request",
                code="lead.conversion.idempotency_conflict",
                context={
                    "lead_id": str(lead.id),
                    "idempotency_key": idempotency_key,
                },
            )
        opportunity = self.opportunities.get(opportunity_id)
        return LeadConversionResult(
            lead=lead,
            opportunity=opportunity,
            created=False,
        )


def _effective_name(value: str | None, lead: Lead) -> str:
    if value is None:
        return f"Lead {lead.id}"
    return " ".join(unicodedata.normalize("NFKC", value).strip().split())


def _normalize_idempotency_key(value: str | None, lead_id: LeadId) -> str:
    if value is None:
        return f"lead-conversion:{lead_id}"
    key = unicodedata.normalize("NFKC", value).strip()
    if not key:
        raise ValidationError(
            "idempotency key cannot be empty",
            code="lead.conversion.idempotency_key.required",
        )
    if len(key) > 255:
        raise ValidationError(
            "idempotency key must be at most 255 characters",
            code="lead.conversion.idempotency_key.too_long",
        )
    return key


def _request_fingerprint(
    *,
    lead_id: LeadId,
    name: str,
    estimated_value: Decimal | None,
    currency: str | None,
    pipeline_id: str | None,
    expected_close_date: date | None,
    owner_id: str | None,
) -> str:
    payload = {
        "lead_id": str(lead_id),
        "name": name,
        "estimated_value": _decimal_token(estimated_value),
        "currency": currency.strip().upper() if currency is not None else None,
        "pipeline_id": pipeline_id.strip().casefold() if pipeline_id is not None else None,
        "expected_close_date": (
            expected_close_date.isoformat() if expected_close_date is not None else None
        ),
        "owner_id": _normalize_optional_token(owner_id),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal_token(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if type(value) is not Decimal:
        raise ValidationError(
            "money amount must be a Decimal",
            code="money.amount.decimal_required",
        )
    if not value.is_finite():
        raise ValidationError(
            "money amount must be finite",
            code="money.amount.non_finite",
        )
    return format(value.normalize(), "f")


def _normalize_optional_token(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    return normalized or None
