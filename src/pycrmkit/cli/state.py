"""State management and local persistence for PyCRMKit CLI."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pycrmkit import CRM
from pycrmkit.cli.state_codec import MAX_STATE_BYTES, CLIStateError, dump_state, load_state
from pycrmkit.communication.email.messages import EmailMessage
from pycrmkit.communication.email.provider import EmailDeliveryStatus, EmailProviderResult
from pycrmkit.contacts import ContactEmail, ContactPhone
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.events import InProcessEventBus
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityQuery
from pycrmkit.pipelines import Stage, StageOutcome, StageTransition
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType
from pycrmkit.storage.memory._state import MemoryStore
from pycrmkit.storage.memory.unit_of_work import MemoryUnitOfWork

DEFAULT_STORE_DIR = Path.home() / ".pycrmkit"
DEFAULT_STORE_FILE = DEFAULT_STORE_DIR / "crm_state.json"
LEGACY_STORE_FILE = DEFAULT_STORE_DIR / "crm_state.pickle"


class MockCliEmailProvider:
    """Simulate local email acceptance, never actual provider delivery."""

    def send(self, message: EmailMessage) -> EmailProviderResult:
        return EmailProviderResult(
            provider="mock-cli-mailer",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=f"msg-cli-{str(message.intent_id)[:8]}",
        )


def _resolve_store_path() -> Path:
    custom = os.getenv("PYCRMKIT_CLI_STATE_FILE")
    if custom:
        return Path(custom)
    return DEFAULT_STORE_FILE


@contextmanager
def _exclusive_state_lock(target: Path) -> Iterator[None]:
    """Lock the entire local read/modify/write transaction using exclusive creation.

    A crash may leave a stale .lock file. Operators must inspect and remove it
    manually after confirming no CLI process still owns that state.
    """
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    if lock_path.is_symlink():
        raise CLIStateError("Unsafe symlink for CLI state lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CLIStateError("Local CLI state is locked by another process") from exc
    except OSError as exc:
        raise CLIStateError("Cannot acquire local CLI state lock") from exc
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _checked_path(target: Path) -> Path:
    if target.suffix.lower() == ".pickle":
        raise CLIStateError("Legacy pickle storage is not supported; archive and re-seed")
    if target.is_symlink():
        raise CLIStateError("Symlink-backed CLI state is not supported")
    if target == DEFAULT_STORE_FILE and LEGACY_STORE_FILE.exists() and not target.exists():
        raise CLIStateError("Legacy pickle state detected; archive it and re-seed a new JSON store")
    return target


def load_store(path: Path | None = None) -> MemoryStore:
    """Read versioned JSON state or initialize a new store; never unpickle files."""
    target = _checked_path(path if path is not None else _resolve_store_path())
    store = MemoryStore()
    if not target.exists():
        return store
    if not target.is_file():
        raise CLIStateError("CLI state path is not a regular file")
    try:
        with target.open("rb") as stream:
            raw = stream.read(MAX_STATE_BYTES + 1)
    except OSError as exc:
        raise CLIStateError("Unable to read local CLI state") from exc
    store._state = load_state(raw)
    return store


def _save_unlocked(store: MemoryStore, target: Path) -> None:
    """Atomic same-filesystem replacement; caller owns any multi-process lock."""
    target = _checked_path(target)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = dump_state(store._state)
    name: str | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=".pycrmkit-state-", suffix=".tmp", dir=target.parent)
        with os.fdopen(fd, "wb") as stream:
            if hasattr(os, "fchmod"):
                os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
        name = None
        if hasattr(os, "O_DIRECTORY"):
            fd_dir = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd_dir)
            finally:
                os.close(fd_dir)
    except OSError as exc:
        raise CLIStateError("Unable to atomically save local CLI state") from exc
    finally:
        if name is not None:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass


def save_store(store: MemoryStore, path: Path | None = None) -> None:
    """Persist versioned state with a per-store exclusive lock and atomic replace."""
    target = path if path is not None else _resolve_store_path()
    with _exclusive_state_lock(target):
        _save_unlocked(store, target)


def build_crm_from_store(store: MemoryStore, actor_id: str | None = None) -> CRM:
    """Build a CRM with a declared actor ID, not an authenticated principal."""
    from pycrmkit.cli.config import resolve_actor_id

    effective_actor = actor_id if actor_id is not None else resolve_actor_id()[0]
    bus = InProcessEventBus()

    def uow_factory() -> MemoryUnitOfWork:
        return MemoryUnitOfWork(store, event_publisher=bus)

    return CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        email_provider=MockCliEmailProvider(),
    ).with_context(actor_id=effective_actor)


def get_database_url() -> str | None:
    """Return the database URL if configured via environment variables or pycrm.yml."""
    from pycrmkit.cli.config import resolve_database_url

    url, _ = resolve_database_url()
    return url


@contextmanager
def get_crm_context(
    save: bool = True,
    actor_id: str | None = None,
    *,
    force_local: bool = False,
) -> Generator[CRM, None, None]:
    """Choose the backend and pass through the effective configured actor claim."""
    from pycrmkit.cli.config import resolve_actor_id

    effective_actor = actor_id if actor_id is not None else resolve_actor_id()[0]
    db_url = None if force_local else get_database_url()
    if db_url:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork

        engine = create_engine(db_url, pool_pre_ping=True)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        bus = InProcessEventBus()

        def uow_factory() -> SQLAlchemyUnitOfWork:
            return SQLAlchemyUnitOfWork(session_factory, event_publisher=bus)

        crm = CRM(
            uow_factory=uow_factory,
            event_bus=bus,
            email_provider=MockCliEmailProvider(),
        ).with_context(actor_id=effective_actor)
        yield crm
    else:
        target = _resolve_store_path()
        if save:
            # Serialize the full read/modify/write transaction, not only the write.
            with _exclusive_state_lock(target):
                store = load_store(target)
                crm = build_crm_from_store(store, actor_id=effective_actor)
                yield crm
                _save_unlocked(store, target)
        else:
            store = load_store(target)
            yield build_crm_from_store(store, actor_id=actor_id)


def query_opportunities(
    crm: CRM,
    query: OpportunityQuery | None = None,
    page: OffsetPageRequest | None = None,
) -> Page[Opportunity]:
    """Query opportunities via CRM runtime unit of work contract."""
    with crm._runtime.uow_factory() as uow:
        return uow.opportunities.list(
            query or OpportunityQuery(),
            page or OffsetPageRequest(),
        )


def get_opportunity(crm: CRM, opportunity_id: OpportunityId) -> Opportunity:
    """Fetch an opportunity via CRM runtime unit of work contract."""
    with crm._runtime.uow_factory() as uow:
        return uow.opportunities.get(opportunity_id)


def seed_demo_data(crm: CRM) -> dict[str, int]:
    """Seed a realistic enterprise B2B dataset covering all core domains."""
    now = datetime.now(UTC)

    # 1. Organizations
    org_curie = crm.organizations.create(
        legal_name="Institut Curie Technologies SAS",
        trading_name="Curie Tech",
        source="partner",
    )
    org_airbus = crm.organizations.create(
        legal_name="Airbus Defense & Space",
        trading_name="Airbus DS",
        source="enterprise_inbound",
    )
    org_total = crm.organizations.create(
        legal_name="TotalEnergies Renewables SA",
        trading_name="TotalEnergies",
        source="outbound_q4",
    )

    # 2. Contacts
    c_marie = crm.contacts.create(
        first_name="Marie",
        last_name="Curie",
        source="referral",
        emails=(
            ContactEmail("marie.curie@curietech.eu", is_primary=True),
            ContactEmail("m.curie@institut.fr"),
        ),
        phones=(ContactPhone("+33 1 42 34 56 78", is_primary=True),),
    )
    c_pierre = crm.contacts.create(
        first_name="Pierre",
        last_name="Curie",
        source="referral",
        emails=(ContactEmail("pierre.curie@curietech.eu", is_primary=True),),
        phones=(ContactPhone("+33 1 42 34 56 79", is_primary=True),),
    )
    c_thomas = crm.contacts.create(
        first_name="Thomas",
        last_name="Pesquet",
        source="inbound",
        emails=(ContactEmail("thomas.pesquet@esa.int", is_primary=True),),
        phones=(ContactPhone("+33 6 12 34 56 78", is_primary=True),),
    )
    crm.contacts.create(
        first_name="Sophie",
        last_name="Germain",
        source="event",
        emails=(ContactEmail("sophie.germain@math.ens.fr", is_primary=True),),
    )
    c_henri = crm.contacts.create(
        first_name="Henri",
        last_name="Poincaré",
        source="outbound",
        emails=(ContactEmail("henri.poincare@polytechnique.edu", is_primary=True),),
        phones=(ContactPhone("+33 1 69 33 40 00", is_primary=True),),
    )

    # 3. Relationships
    crm.relationships.create(
        source=RelationshipEndpoint.contact(c_marie.id),
        target=RelationshipEndpoint.organization(org_curie.id),
        relationship_type=RelationshipType("employee_of"),
        role="Directrice Scientifique",
        is_primary=True,
    )
    crm.relationships.create(
        source=RelationshipEndpoint.contact(c_pierre.id),
        target=RelationshipEndpoint.organization(org_curie.id),
        relationship_type=RelationshipType("employee_of"),
        role="Directeur de Recherche",
        is_primary=False,
    )
    crm.relationships.create(
        source=RelationshipEndpoint.contact(c_thomas.id),
        target=RelationshipEndpoint.organization(org_airbus.id),
        relationship_type=RelationshipType("employee_of"),
        role="Lead Ingénieur Spatial",
        is_primary=True,
    )
    crm.relationships.create(
        source=RelationshipEndpoint.contact(c_henri.id),
        target=RelationshipEndpoint.organization(org_total.id),
        relationship_type=RelationshipType("employee_of"),
        role="VP Innovation & Transition",
        is_primary=True,
    )

    # 4. Sales Pipeline & Stages
    pipeline_id = "b2b-enterprise"
    crm.pipelines.define(
        id=pipeline_id,
        name="Vente Entreprise B2B",
        stages=(
            Stage("qualification", "Qualification", 0, Decimal("0.20")),
            Stage("demo", "Démonstration", 1, Decimal("0.50")),
            Stage("proposal", "Proposition", 2, Decimal("0.80")),
            Stage("won", "Gagné (Won)", 3, terminal=True, outcome=StageOutcome.WON),
            Stage("lost", "Perdu (Lost)", 4, terminal=True, outcome=StageOutcome.LOST),
        ),
        transitions=(
            StageTransition("qualification", "demo"),
            StageTransition("demo", "proposal"),
            StageTransition("proposal", "won"),
            StageTransition("proposal", "lost"),
            StageTransition("qualification", "lost"),
            StageTransition("demo", "lost"),
        ),
    )

    # 5. Opportunities
    # Opp 1: Proposal stage (80%)
    opp1 = crm.opportunities.create(
        name="Calculateur Quantique Curie",
        pipeline_id=pipeline_id,
        stage_id="qualification",
        estimated_value=Decimal("150000.00"),
        currency="EUR",
        probability=Decimal("0.20"),
        organization_id=org_curie.id,
        contact_id=c_marie.id,
    )
    crm.opportunities.move(opp1.id, to="demo")
    crm.opportunities.move(opp1.id, to="proposal")

    # Opp 2: Demo stage (50%)
    opp2 = crm.opportunities.create(
        name="Télémétrie Spatiale Avancée",
        pipeline_id=pipeline_id,
        stage_id="qualification",
        estimated_value=Decimal("220000.00"),
        currency="EUR",
        probability=Decimal("0.20"),
        organization_id=org_airbus.id,
        contact_id=c_thomas.id,
    )
    crm.opportunities.move(opp2.id, to="demo")

    # Opp 3: Won (100%)
    opp3 = crm.opportunities.create(
        name="Monitoring Énergétique IA",
        pipeline_id=pipeline_id,
        stage_id="qualification",
        estimated_value=Decimal("85000.00"),
        currency="EUR",
        probability=Decimal("0.20"),
        organization_id=org_total.id,
        contact_id=c_henri.id,
    )
    crm.opportunities.move(opp3.id, to="demo")
    crm.opportunities.move(opp3.id, to="proposal")
    crm.opportunities.move(opp3.id, to="won")

    # Opp 4: Qualification (20%)
    crm.opportunities.create(
        name="Audit Cyber-Résilience",
        pipeline_id=pipeline_id,
        stage_id="qualification",
        estimated_value=Decimal("30000.00"),
        currency="EUR",
        probability=Decimal("0.20"),
        organization_id=org_curie.id,
        contact_id=c_pierre.id,
    )

    # 6. Campaigns
    camp1 = crm.campaigns.create(
        key="summit-europe-2026",
        name="Tech Summit Europe 2026",
        description="Campagne multi-canal de lancement du sommet tech européen",
        starts_at=now,
        ends_at=now + timedelta(days=60),
        metadata={"budget_allocated": 75000},
    )
    crm.campaigns.add_member(camp1.id, EntityReference("contact", c_marie.id), source="vip_list")
    crm.campaigns.add_member(
        camp1.id, EntityReference("contact", c_thomas.id), source="speaker_invite"
    )
    crm.campaigns.add_member(camp1.id, EntityReference("contact", c_henri.id), source="vip_list")
    crm.campaigns.activate(camp1.id)

    camp2 = crm.campaigns.create(
        key="q4-executive-briefing",
        name="Dîner Décideurs Tech Q4",
        description="Rencontre restreinte C-Level",
        starts_at=now,
        ends_at=now + timedelta(days=20),
        metadata={"budget_allocated": 25000},
    )
    crm.campaigns.add_member(camp2.id, EntityReference("contact", c_marie.id), source="direct")
    crm.campaigns.add_member(camp2.id, EntityReference("contact", c_pierre.id), source="direct")
    crm.campaigns.activate(camp2.id)

    # 7. Tags (v1.2.0)
    tag_client = crm.tags.create("client")
    tag_vip = crm.tags.create("vip")
    tag_deeptech = crm.tags.create("deeptech")
    tag_saas = crm.tags.create("saas")

    crm.tags.assign(tag_client.id, EntityReference("organization", org_curie.id))
    crm.tags.assign(tag_vip.id, EntityReference("organization", org_curie.id))
    crm.tags.assign(tag_deeptech.id, EntityReference("organization", org_curie.id))
    crm.tags.assign(tag_saas.id, EntityReference("organization", org_curie.id))
    crm.tags.assign(tag_client.id, EntityReference("contact", c_marie.id))
    crm.tags.assign(tag_vip.id, EntityReference("contact", c_marie.id))
    crm.tags.assign(tag_client.id, EntityReference("organization", org_airbus.id))
    crm.tags.assign(tag_vip.id, EntityReference("contact", c_thomas.id))

    # 8. Custom Fields (v1.2.0)
    cf_sector = crm.custom_fields.define(
        key="sector",
        label="Secteur",
        field_type=CustomFieldType.STRING,
        applies_to=("organization", "contact"),
    )
    cf_segment = crm.custom_fields.define(
        key="segment",
        label="Segment",
        field_type=CustomFieldType.STRING,
        applies_to=("organization", "contact"),
    )
    cf_contract = crm.custom_fields.define(
        key="contract_duration",
        label="Durée contrat",
        field_type=CustomFieldType.STRING,
        applies_to=("organization",),
    )

    crm.custom_fields.set_value(
        cf_sector.id,
        EntityReference("organization", org_curie.id),
        "Biotechnologies & IA",
    )
    crm.custom_fields.set_value(
        cf_segment.id,
        EntityReference("organization", org_curie.id),
        "Stratégique Tier 1",
    )
    crm.custom_fields.set_value(
        cf_contract.id,
        EntityReference("organization", org_curie.id),
        "36 mois",
    )
    crm.custom_fields.set_value(
        cf_sector.id,
        EntityReference("contact", c_marie.id),
        "Physique Quantique",
    )
    crm.custom_fields.set_value(
        cf_segment.id,
        EntityReference("contact", c_marie.id),
        "C-Level / Décideur",
    )

    # 9. Tasks & Activities
    crm.tasks.create(
        title="Préparer démonstration télémétrie spatiale pour Thomas Pesquet",
        due_at=now + timedelta(days=2),
        priority="high",
        references=(EntityReference("contact", c_thomas.id),),
    )
    t2 = crm.tasks.create(
        title="Finaliser contrat de licence TotalEnergies",
        due_at=now,
        priority="normal",
        references=(EntityReference("organization", org_total.id),),
    )
    crm.tasks.complete(t2.id)

    crm.tasks.create(
        title="Valider la proposition finale Calculateur Quantique",
        due_at=now + timedelta(days=5),
        priority="high",
        references=(
            EntityReference("organization", org_curie.id),
            EntityReference("contact", c_marie.id),
        ),
    )
    crm.tasks.create(
        title="Planifier le point trimestriel QBR avec Marie Curie",
        due_at=now + timedelta(days=12),
        priority="normal",
        references=(
            EntityReference("organization", org_curie.id),
            EntityReference("contact", c_marie.id),
        ),
    )

    crm.activities.log(
        type="meeting",
        subject="Revue de cadrage technique et architecture cloud",
        references=(
            EntityReference("contact", c_marie.id),
            EntityReference("organization", org_curie.id),
        ),
    )
    crm.activities.log(
        type="call",
        subject="Point commercial préliminaire - Validation des modules",
        references=(
            EntityReference("contact", c_marie.id),
            EntityReference("organization", org_curie.id),
        ),
    )
    crm.activities.log(
        type="note",
        subject="Intérêt très fort confirmé pour l'intégration de modules IA et support 24/7",
        references=(
            EntityReference("contact", c_marie.id),
            EntityReference("organization", org_curie.id),
        ),
    )

    return {
        "organizations": 3,
        "contacts": 5,
        "opportunities": 4,
        "campaigns": 2,
        "tasks": 4,
    }
