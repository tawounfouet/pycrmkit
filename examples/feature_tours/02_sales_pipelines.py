#!/usr/bin/env python3
"""PyCRMKit 1.2.0 - Feature Tour 02: Sales Pipelines & Lead Conversion.

Demonstrates and verifies:
- Lead capture and qualification
- Commercial Pipeline configuration (Stages, win probabilities, terminal outcomes)
- Idempotent Lead Conversion into Opportunity + Contact + Organization
- Opportunity stage progression and transition invariants enforcement
- Rejection of illegal stage regressions via InvalidStageTransition
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pycrmkit import CRM, __version__
from pycrmkit.contacts import ContactEmail
from pycrmkit.pipelines import (
    Stage,
    StageOutcome,
    StageTransition,
    InvalidStageTransition,
)


def run_tour() -> dict[str, object]:
    print("=" * 70)
    print("📈 PYCRMKIT FEATURE TOUR 02: SALES PIPELINES & LEAD CONVERSION")
    print(f"📦 PyCRMKit Version: {__version__}")
    print("=" * 70)

    # 1. Initialization
    crm = CRM.memory().with_context(
        actor_id="sales-executive-42",
        correlation_id="sales-tour-session",
    )
    print(f"\n[1/6] CRM In-Memory initialisé (Acteur: {crm.context.actor_id})")

    # 2. Lead Capture
    org = crm.organizations.create(legal_name="Aerospace Dynamics Group")
    contact = crm.contacts.create(
        first_name="Alan",
        last_name="Turing",
        emails=(ContactEmail("alan.turing@aerospace-dyn.com", is_primary=True),),
    )
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=org.id,
        source="trade_show_inbound",
    )
    print(f"[2/6] Lead capturé : [ID: {lead.id}] (Statut initial: {lead.status.value})")

    qualified_lead = crm.leads.qualify(lead.id)
    print(f"      Lead qualifié avec succès : Statut -> {qualified_lead.status.value}")

    # 3. Pipeline Definition
    stages = (
        Stage("qualification", "Qualification & Cadrage", 0, Decimal("0.20")),
        Stage("demo", "Démonstration Technique", 1, Decimal("0.50")),
        Stage("proposal", "Offre & Négociation", 2, Decimal("0.80")),
        Stage("won", "Gagné / Contrat Signé", 3, terminal=True, outcome=StageOutcome.WON),
        Stage("lost", "Perdu", 4, terminal=True, outcome=StageOutcome.LOST),
    )
    transitions = (
        StageTransition("qualification", "demo"),
        StageTransition("demo", "proposal"),
        StageTransition("proposal", "won"),
        StageTransition("proposal", "lost"),
        StageTransition("qualification", "lost"),
        StageTransition("demo", "lost"),
    )
    pipeline = crm.pipelines.define(
        id="enterprise-b2b",
        name="Vente Complexe B2B",
        stages=stages,
        transitions=transitions,
    )
    print(f"[3/6] Pipeline configuré : '{pipeline.name}' [ID: {pipeline.id}]")
    print(f"      Étape de départ : '{pipeline.initial_stage.name}' (Probabilité: {pipeline.initial_stage.default_probability * 100:.0f}%)")

    # 4. Lead Conversion
    opportunity = crm.leads.convert(
        lead_id=qualified_lead.id,
        name="Déploiement Calculateur Haute Performance",
        estimated_value=Decimal("150000.00"),
        currency="EUR",
        pipeline_id=pipeline.id,
        idempotency_key="conv-turing-aerospace-2026",
    )
    print(f"[4/6] Lead converti en Opportunité : '{opportunity.name}'")
    print(f"      Valeur estimée : {opportunity.estimated_value} {opportunity.currency} | Étape : {opportunity.stage_id}")

    # Test Idempotency
    retry_opp = crm.leads.convert(
        lead_id=qualified_lead.id,
        name="Déploiement Calculateur Haute Performance",
        estimated_value=Decimal("150000.00"),
        currency="EUR",
        pipeline_id=pipeline.id,
        idempotency_key="conv-turing-aerospace-2026",
    )
    assert retry_opp.id == opportunity.id
    print("      Idempotence vérifiée : La tentative de conversion rejouée renvoie l'opportunité existante.")

    # 5. Opportunity Progression
    opportunity = crm.opportunities.move(opportunity.id, to="demo")
    print(f"[5/6] Progression vers '{opportunity.stage_id}' (Probabilité: {opportunity.probability * 100:.0f}%)")

    opportunity = crm.opportunities.move(opportunity.id, to="proposal")
    print(f"      Progression vers '{opportunity.stage_id}' (Probabilité: {opportunity.probability * 100:.0f}%)")

    # Guard: Invalid Transition
    try:
        crm.opportunities.move(opportunity.id, to="qualification")
        raise RuntimeError("ERREUR: La régression non autorisée a été acceptée !")
    except InvalidStageTransition as exc:
        print(f"      🛡️ Invariant vérifié : Transition interdite bloquée -> {exc}")

    # 6. Closing Won
    opportunity = crm.opportunities.move(opportunity.id, to="won")
    print(f"[6/6] Opportunité clôturée avec succès : Statut -> {opportunity.status.value}")
    print(f"      Valeur finale remportée : {opportunity.estimated_value} {opportunity.currency} (Probabilité: {opportunity.probability * 100:.0f}%)")

    # Integrity Assertions
    assert qualified_lead.status.value == "qualified"
    assert opportunity.status.value == "won"
    assert opportunity.probability == Decimal("1")
    assert opportunity.estimated_value == Decimal("150000.00")

    print("\n" + "=" * 70)
    print("✅ FEATURE TOUR 02 TERMINÉ AVEC SUCCÈS (Toutes les assertions vérifiées)")
    print("=" * 70 + "\n")

    return {
        "tour": "02_sales_pipelines",
        "lead_id": str(lead.id),
        "opportunity_id": str(opportunity.id),
        "pipeline_id": pipeline.id,
        "final_status": opportunity.status.value,
        "status": "PASS",
    }


if __name__ == "__main__":
    run_tour()
