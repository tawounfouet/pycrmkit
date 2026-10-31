#!/usr/bin/env python3
"""PyCRMKit 1.2.0 - Feature Tour 05: Segmentation & Saved Queries.

Demonstrates and verifies:
- Creation and population of Contacts and Organizations
- Static Segments with explicit member inclusions & containment checks
- Dynamic Segments evaluated in real time via AST Predicates
- Audience Snapshotting: freezing dynamic segment results at point-in-time
- Immutability of Snapshots upon subsequent contact additions
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pycrmkit import CRM, __version__
from pycrmkit.core.references import EntityReference
from pycrmkit.segments import Predicate, QueryOperator, SegmentMode


def run_tour() -> dict[str, object]:
    print("=" * 70)
    print("🎯 PYCRMKIT FEATURE TOUR 05: SEGMENTATION & SAVED QUERIES")
    print(f"📦 PyCRMKit Version: {__version__}")
    print("=" * 70)

    # 1. Initialization & Population
    crm = CRM.memory().with_context(
        actor_id="marketing-lead-11",
        correlation_id="segment-tour-session",
    )
    print(f"\n[1/5] CRM initialisé (Acteur: {crm.context.actor_id})")

    c1 = crm.contacts.create(first_name="Alice", last_name="Dubois", source="linkedin")
    c2 = crm.contacts.create(first_name="Bernard", last_name="Lemoine", source="linkedin")
    c3 = crm.contacts.create(first_name="Claire", last_name="Moreau", source="webinar")
    c4 = crm.contacts.create(first_name="David", last_name="Rousseau", source="cold_call")
    print(f"[2/5] Base de contacts peuplée : 4 contacts créés avec sources distinctes")

    # 2. Static Segment
    static_seg = crm.segments.create_static(
        key="vip-clients-france",
        name="Clients VIP France",
        entity_kind="contact",
        description="Liste sélectionnée manuellement par le management",
    )
    crm.segments.add_member(static_seg.id, EntityReference("contact", c1.id))
    crm.segments.add_member(static_seg.id, EntityReference("contact", c3.id))

    print(f"[3/5] Segment Statique créé : '{static_seg.name}' [Mode: {static_seg.mode.value}]")
    print(f"      Nombre de membres : {crm.segments.count(static_seg.id)}")
    print(f"      Alice est membre ? {crm.segments.contains(static_seg.id, EntityReference('contact', c1.id))}")
    print(f"      David est membre ? {crm.segments.contains(static_seg.id, EntityReference('contact', c4.id))}")

    # 3. Dynamic Segment via Query Predicates
    dyn_seg = crm.segments.create_dynamic(
        key="leads-linkedin-france",
        name="Prospects LinkedIn",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
        description="Audience calculée dynamiquement sur la source 'linkedin'",
    )
    print(f"[4/5] Segment Dynamique créé : '{dyn_seg.name}' [Mode: {dyn_seg.mode.value}]")
    evaluated_members = crm.segments.evaluate(dyn_seg.id).items
    print(f"      Évaluation en temps réel : {len(evaluated_members)} membre(s) détecté(s)")
    for ref in evaluated_members:
        print(f"      • [{ref.kind}] {ref.id}")

    # 4. Audience Snapshot
    snapshot = crm.segments.snapshot(
        dyn_seg.id,
        key="snapshot-linkedin-q4",
        name="Snapshot Figé LinkedIn Q4",
    )
    print(f"[5/5] Snapshot d'audience créé : '{snapshot.name}' [Mode: {snapshot.mode.value}]")
    print(f"      Taille initiale du snapshot : {crm.segments.count(snapshot.id)} membres")

    # 5. Invariance Demonstration: Add new contact
    c5 = crm.contacts.create(first_name="Emma", last_name="Laurent", source="linkedin")
    print(f"      Nouveau contact créé avec source 'linkedin' : {c5.first_name} {c5.last_name}")
    print(f"      -> Taille segment dynamique mise à jour : {crm.segments.count(dyn_seg.id)}")
    print(f"      -> Taille du snapshot figé (inchangée)   : {crm.segments.count(snapshot.id)}")

    # Assertions
    assert static_seg.mode is SegmentMode.STATIC
    assert dyn_seg.mode is SegmentMode.DYNAMIC
    assert snapshot.mode is SegmentMode.SNAPSHOT
    assert crm.segments.count(static_seg.id) == 2
    assert crm.segments.count(dyn_seg.id) == 3
    assert crm.segments.count(snapshot.id) == 2
    assert crm.segments.contains(static_seg.id, EntityReference("contact", c1.id)) is True
    assert crm.segments.contains(static_seg.id, EntityReference("contact", c4.id)) is False

    print("\n" + "=" * 70)
    print("✅ FEATURE TOUR 05 TERMINÉ AVEC SUCCÈS (Toutes les assertions vérifiées)")
    print("=" * 70 + "\n")

    return {
        "tour": "05_segmentation_queries",
        "static_segment_count": crm.segments.count(static_seg.id),
        "dynamic_segment_count": crm.segments.count(dyn_seg.id),
        "snapshot_count": crm.segments.count(snapshot.id),
        "status": "PASS",
    }


if __name__ == "__main__":
    run_tour()
