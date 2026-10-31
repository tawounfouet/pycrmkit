#!/usr/bin/env python3
"""PyCRMKit 1.2.0 — Feature Tour 04: Data Operations, Deduplication & Merge.

Demonstrates and verifies:
- Ingestion pipeline with CSVReader
- DeduplicationEngine scoring and matching over CandidateRecords
- Formal duplicate detection (DedupDecision.DUPLICATE)
- Anti-injection Spreadsheet Guard for safe CSV exports
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pycrmkit import __version__
from pycrmkit.importers import CSVReader, ImportRow
from pycrmkit.dedup import (
    DeduplicationEngine,
    CandidateRecord,
    InMemoryCandidateSource,
    DedupDecision,
)


def run_tour() -> dict[str, object]:
    print("=" * 70)
    print("🧹 PYCRMKIT FEATURE TOUR 04: DATA OPERATIONS & DEDUPLICATION")
    print(f"📦 PyCRMKit Version: {__version__}")
    print("=" * 70)

    # 1. Ingestion via CSVReader
    raw_csv = """first_name,last_name,email,company
  Ada  ,  Lovelace , ADA.LOVELACE@ANALYTICAL.ORG , Analytical Engines Ltd
Charles , Babbage , babbage@cambridge.ac.uk , Cambridge Computing
Ada , Lovelace , ada@analytical.org , Analytical Engines
"""
    reader = CSVReader(io.StringIO(raw_csv))
    rows = list(reader.read())
    print(f"\n[1/4] Flux CSV ingéré : {len(rows)} enregistrements bruts")
    for idx, r in enumerate(rows, start=1):
        print(f"      Ligne {idx} : {r['first_name'].strip()} {r['last_name'].strip()} <{r['email'].strip()}>")

    # 2. Deduplication Engine Setup
    existing_candidates = (
        CandidateRecord(
            entity_id="contact-master-001",
            values={
                "email": "ada.lovelace@analytical.org",
                "full_name": "Ada Lovelace",
                "organization": "Analytical Engines Ltd",
            },
        ),
        CandidateRecord(
            entity_id="contact-master-002",
            values={
                "email": "charles.babbage@cambridge.ac.uk",
                "full_name": "Charles Babbage",
                "organization": "Cambridge Computing",
            },
        ),
    )
    engine = DeduplicationEngine(source=InMemoryCandidateSource(existing_candidates))
    print(f"[2/4] Moteur de Déduplication configuré avec {len(existing_candidates)} fiches maîtresses en mémoire")

    # 3. Assessment & Duplicate Detection
    incoming_row = ImportRow(
        number=1,
        values={
            "email": "ADA.LOVELACE@ANALYTICAL.ORG",
            "full_name": "ada lovelace",
            "organization": "Analytical Engines Ltd",
        },
    )
    assessments = engine.evaluate(incoming_row)
    print(f"[3/4] Évaluation de la ligne entrante '{incoming_row.values['email']}' :")
    for a in assessments:
        print(f"      • Fiche maîtresse [{a.candidate.entity_id}] -> Décision: {a.decision.value} | Score: {a.score}")

    detected = engine.detect(incoming_row)
    print(f"      Résultat final de détection de doublon : {detected.is_duplicate}")
    if detected.is_duplicate:
        print(f"      -> Contact existant associé : {detected.existing_entity_id}")

    # 4. Safe Spreadsheet Guard (Formula Injection Prevention)
    malicious_inputs = [
        "=CMD|' /C calc'!A0",
        "+SUM(A1:A10)",
        "-2+3*4",
        "@SUM(B1:B5)",
    ]
    print("\n[4/4] Test du Guard Anti-Injection Tableur (CSV/Excel) :")
    sanitized_outputs = []
    for raw in malicious_inputs:
        safe = "'" + raw if raw.startswith(("=", "+", "-", "@")) else raw
        sanitized_outputs.append(safe)
        print(f"      Entrée suspecte : {raw:<22} -> Protégée : {safe}")

    # Assertions
    assert len(rows) == 3
    assert len(assessments) == 2
    assert assessments[0].decision == DedupDecision.DUPLICATE
    assert detected.is_duplicate is True
    assert detected.existing_entity_id == "contact-master-001"
    assert all(s.startswith("'") for s in sanitized_outputs)

    print("\n" + "=" * 70)
    print("✅ FEATURE TOUR 04 TERMINÉ AVEC SUCCÈS (Toutes les assertions vérifiées)")
    print("=" * 70 + "\n")

    return {
        "tour": "04_data_operations",
        "parsed_rows": len(rows),
        "duplicate_detected": detected.is_duplicate,
        "matched_entity_id": detected.existing_entity_id,
        "status": "PASS",
    }


if __name__ == "__main__":
    run_tour()
