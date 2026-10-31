#!/usr/bin/env python3
"""PyCRMKit 1.2.0 — Feature Tour 01: Core CRM Foundations.

Demonstrates and verifies:
- CRM.memory() initialization with audit context
- Contacts (display name, email normalization, phone records)
- Organizations (legal entity, trading name, hierarchy)
- Relationships (Contact <-> Organization with roles & is_primary)
- Tags and typed Custom Fields
- Activities logging and Task lifecycle with Business Calendar
- Unified chronological Timeline aggregation
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure pycrmkit package from src is accessible
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pycrmkit import CRM, __version__
from pycrmkit.contacts import ContactEmail, ContactPhone
from pycrmkit.core.references import EntityReference
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.calendars import BusinessCalendar
from pycrmkit.tasks import TaskPriority


def run_tour() -> dict[str, object]:
    print("=" * 70)
    print("🚀 PYCRMKIT FEATURE TOUR 01: CORE CRM FOUNDATIONS")
    print(f"📦 PyCRMKit Version: {__version__}")
    print("=" * 70)

    # 1. CRM.memory() initialization
    crm = CRM.memory().with_context(
        actor_id="admin-user-001",
        correlation_id="core-tour-session",
    )
    print(f"\n[1/7] CRM In-Memory initialisé (Acteur: {crm.context.actor_id})")

    # 2. Organization creation
    org = crm.organizations.create(
        legal_name="Institut Curie Technologies SAS",
        trading_name="Curie Tech Labs",
        source="feature-tour",
    )
    print(f"[2/7] Organisation créée : {org.legal_name} [ID: {org.id}]")

    # 3. Contact creation
    contact = crm.contacts.create(
        first_name="Marie",
        last_name="Curie",
        source="feature-tour",
        emails=(ContactEmail("Marie.Curie@Institut-Curie.org", is_primary=True),),
        phones=(ContactPhone("+33 1 42 34 60 00", is_primary=True),),
    )
    print(f"[3/7] Contact créé : {contact.display_name}")
    print(f"      Email normalisé : {contact.emails[0].normalized}")

    # 4. Relationship Contact <-> Organization
    rel = crm.relationships.create(
        source=RelationshipEndpoint.contact(contact.id),
        target=RelationshipEndpoint.organization(org.id),
        relationship_type=RelationshipType("employee_of"),
        role="Directrice de Recherche",
        is_primary=True,
    )
    print(f"[4/7] Relation établie : {contact.display_name} -> {rel.role} chez {org.legal_name} (Principal: {rel.is_primary})")

    # 5. Tags & Custom Fields
    vip_tag = crm.tags.create(name="Strategic Account")
    crm.tags.assign(tag_id=vip_tag.id, entity=EntityReference("contact", contact.id))

    field_def = crm.custom_fields.define(
        key="clearance_level",
        label="Niveau d'accréditation",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    field_val = crm.custom_fields.set_value(
        definition_id=field_def.id,
        entity=EntityReference("contact", contact.id),
        value="Secret Défense",
    )
    print(f"[5/7] Tag assigné : '{vip_tag.name}' & Custom field '{field_def.label}' = '{field_val.value}'")

    # 6. Activities, Business Calendar & Tasks
    contact_ref = EntityReference("contact", contact.id)
    activity = crm.activities.log(
        type="meeting",
        subject="Revue de partenariat scientifique",
        direction="inbound",
        references=(contact_ref,),
    )

    calendar = BusinessCalendar(key="fr-workdays", timezone="Europe/Paris")
    crm.calendars.register(calendar)
    due_date = crm.calendars.due_in_business_days("fr-workdays", days=4)

    task = crm.tasks.create(
        title="Envoyer la convention de recherche",
        priority=TaskPriority.HIGH,
        due_at=due_date,
        references=(contact_ref,),
    )
    completed_task = crm.tasks.complete(task.id)
    print(f"[6/7] Activité consignée : '{activity.subject}'")
    print(f"      Tâche créée avec échéance ouvrée ({task.due_at.strftime('%Y-%m-%d')}) et complétée : {completed_task.status.value}")

    # 7. Timeline Aggregation
    timeline = crm.timeline.for_contact(contact.id)
    print(f"[7/7] Timeline pour {contact.display_name} ({timeline.total} événements enregistrés) :")
    for item in timeline.items:
        print(f"      • [{item.event_type}] {item.title}")

    # Integrity Assertions
    assert org.id is not None
    assert contact.emails[0].normalized == "marie.curie@institut-curie.org"
    assert rel.is_primary is True
    assert field_val.value == "Secret Défense"
    assert completed_task.status.value == "completed"
    assert timeline.total >= 3

    print("\n" + "=" * 70)
    print("✅ FEATURE TOUR 01 TERMINÉ AVEC SUCCÈS (Toutes les assertions vérifiées)")
    print("=" * 70 + "\n")

    return {
        "tour": "01_core_crm",
        "contact_id": str(contact.id),
        "organization_id": str(org.id),
        "timeline_events": timeline.total,
        "status": "PASS",
    }


if __name__ == "__main__":
    run_tour()
