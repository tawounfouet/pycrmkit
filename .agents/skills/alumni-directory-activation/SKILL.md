---
name: alumni-directory-activation
description: >
  Manage the complete alumni directory creation and account activation funnel for alumni networks
  and higher education associations using PyCRMKit and Django: ingest Google Forms CSV/Excel responses
  with anti-injection sanitization, run fuzzy deduplication, coordinate cohort ambassadors (référents
  de promo), track tokenized email invitations (/activate?token=...), monitor activation drop-offs,
  and automate J+7 reminder batches.
user-invocable: true
---

# Alumni Directory & Network Activation (`alumni-directory-activation`)

Use this skill when deploying, populating, and activating a verified alumni directory for higher education institutions, engineering schools, universities, or alumni associations integrating with Django.

* **Detailed Funnel Architecture & Multi-Team Workflow** : [`workflow.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/alumni-directory-activation/workflow.md)
* **Real-World Examples & CLI Recipes** : [`examples.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/alumni-directory-activation/examples.md)

---

## Core Rules

1. **Assainissement Anti-Injection Tableur** : Tout import de fichier CSV ou Excel provenant de Google Forms doit neutraliser les formules malveillantes débutant par `=`, `+`, `-`, `@` avant ingestion.
2. **Déduplication Déterministe puis Floue** : Vérifier d'abord l'existence de l'alumni par son email principal normalisé, puis par similarité floue sur le triplet `(nom, prénom, année_promo)` avec score de confiance minimum de 85%.
3. **Traçabilité des Référents de Promo** : Chaque promotion (`promo-YYYY`) dispose d'un ou deux référents identifiés par la relation `ambassador_of` dans PyCRMKit pour co-animer le réseau.
4. **Jeton d'Invitation Unique & Horodaté** : Toute invitation émise doit générer un token d'activation sécurisé avec une durée de vie définie (14 jours) consigné dans la Timeline.
5. **Relance Ciblée J+7** : Tout contact n'ayant pas activé son compte sous 7 jours après l'envoi de l'invitation bascule au stage `relance_j7` et fait l'objet d'un rapport de relance pour le référent de promo.
6. **Synchronisation d'Activation Django** : Le clic et la validation du mot de passe sur `/activate` déclenchent la transition vers `compte_active` (100% Won) et l'activation du compte Django (`user.is_active = True`).

---

## Operating Workflows

### 1. Ingestion Sécurisée des Réponses Google Forms

Lorsqu'un lot de réponses exporté de Google Forms (CSV ou Excel) est reçu :

```bash
# 1. Création de la fiche contact avec ses attributs d'identité
pck contacts create \
    --first-name "Patrice" \
    --last-name "Tchamba" \
    --email "patrice.tchamba@techcorp.com" \
    --phone "+33612345678"

# 2. Ajout des tags de promotion et d'annuaire
pck contacts update <contact-id> \
    --tags "promo-2019,genie-logiciel,alumni-actif"

# 3. Création de l'opportunité dans le pipeline d'activation
pck sales opps create \
    --contact <contact-id> \
    --title "Activation Annuaire Django - Patrice Tchamba" \
    --pipeline "alumni-directory-activation" \
    --stage "formulaire_ingere" \
    --value 0
```

En Python avec validation anti-injection et Custom Fields annuaire :

```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()

# Création du contact avec les Custom Fields de l'annuaire
contact = crm.contacts.create(
    first_name="Patrice",
    last_name="Tchamba",
    email="patrice.tchamba@techcorp.com",
    phone="+33612345678",
    tags={"promo-2019", "genie-logiciel"},
    custom_fields={
        "promo_year": 2019,
        "specialization": "Génie Logiciel",
        "current_company": "TechCorp Solutions",
        "current_position": "Lead Software Architect",
        "linkedin_url": "https://linkedin.com/in/ptchamba",
        "willing_to_mentor": True,
        "activation_status": "pending_invite",
    },
)

# Attachement de l'identité externe Google Forms
contact.add_external_identity(
    system="google_forms_alumni_2026",
    external_id="RESP-2026-0492",
)
crm.contacts.save(contact)
```

---

### 2. Déduplication et Réconciliation des Profils

Pour éviter d'écraser un compte existant ou de créer un doublon lorsqu'un alumni soumet le formulaire plusieurs fois :

```python
# Recherche de doublons par email ou similarité nom/prénom/promo
duplicates = crm.contacts.find_duplicates(
    email="patrice.tchamba@techcorp.com",
    name=("Patrice", "Tchamba"),
    fuzzy_threshold=0.85,
)

if duplicates:
    existing_contact = duplicates[0]
    # Fusion intelligente : enrichissement des champs manquants
    crm.contacts.merge(
        target_contact_id=existing_contact.id,
        source_contact_id=contact.id,
        strategy="enrich_missing",
    )
    crm.timeline.record_note(
        contact_id=existing_contact.id,
        content="Formulaire alumni réconcilié et fusionné avec profil existant.",
    )
```

---

### 3. Envoi de l'Invitation d'Activation avec Jeton

Lors de la diffusion de la campagne d'activation (en masse ou au fil de l'eau) :

```python
import secrets
from datetime import datetime, timedelta

# Génération du jeton d'activation sécurisé
activation_token = secrets.token_urlsafe(32)
expiration_date = datetime.now() + timedelta(days=14)

# Mise à jour des Custom Fields du contact
contact.custom_fields["activation_token"] = activation_token
contact.custom_fields["activation_token_expires_at"] = expiration_date.isoformat()
contact.custom_fields["activation_status"] = "invite_sent"
crm.contacts.save(contact)

# Consignation de l'événement dans la Timeline
crm.timeline.record_activity(
    contact_id=contact.id,
    type="email_sent",
    title="Invitation à l'Annuaire Django envoyée",
    description=f"Lien d'activation émis : https://alumni.ecole.org/activate?token={activation_token}",
)

# Transition de l'opportunité vers invitation_envoyee
crm.pipelines.transition(
    opportunity_id="opp_activation_patrice",
    to_stage="invitation_envoyee",
    metadata={"token_sent_at": datetime.now().isoformat()},
)
```

---

### 4. Suivi d'Inactivité & Coordination Référents de Promo (J+7)

Lorsqu'un ensemble d'invitations reste sans activation au bout de 7 jours :

```bash
# Identifier les opportunités bloquées à invitation_envoyee
pck sales opps list \
    --pipeline "alumni-directory-activation" \
    --stage "invitation_envoyee"
```

En Python, génération du rapport de relance pour le référent de promo :

```python
# Trouver les contacts non activés de la promo 2019
promo_2019_pending = crm.contacts.filter(
    lambda c: "promo-2019" in c.tags and c.custom_fields.get("activation_status") == "invite_sent"
)

# Liste prête à être transmise sur WhatsApp au référent de promo
whatsapp_summary = "📢 Relance Annuaire Promo 2019 :\n"
for c in promo_2019_pending:
    whatsapp_summary += f"- {c.first_name} {c.last_name} ({c.email})\n"
```

---

### 5. Finalisation de l'Activation sur Django (100% Won)

Lorsque l'alumni soumet le formulaire `/activate` avec son mot de passe :

```python
# Validation du token et activation du User Django
# 1. Passage du stage à compte_active (100% Won)
crm.pipelines.transition(
    opportunity_id="opp_activation_patrice",
    to_stage="compte_active",
    metadata={"activated_at": datetime.now().isoformat()},
)

# 2. Mise à jour des statuts annuaire
contact.custom_fields["activation_status"] = "activated"
contact.custom_fields["directory_visibility"] = "public_verified"
crm.contacts.save(contact)

# 3. Trace indélébile dans la Timeline
crm.timeline.record_activity(
    contact_id=contact.id,
    type="account_activated",
    title="Compte Alumni Django activé avec succès 🎉",
    description="Mot de passe initialisé. Profil vérifié et visible dans l'annuaire.",
)
```

---

## Pipeline `alumni-directory-activation`

| Stage ID | Nom Affiché | Probabilité | Action Requise |
|---|---|---|---|
| `formulaire_ingere` | Formulaire Reçu & Dédupliqué | 20 % | Vérification anti-injection, création contact & opportunité. |
| `fiche_qualifiee` | Fiche Qualifiée & Prête | 40 % | Validation des champs obligatoires (promo, email valide). |
| `invitation_envoyee` | Invitation & Jeton Transmis | 60 % | Envoi de l'email avec lien `/activate?token=...`. |
| `relance_j7` | Relance J+7 (Alerte Référent) | 50 % | Notification du référent de promo et relance email. |
| `compte_active` | Compte Activé & Annuaire Opérationnel | 100 % (Won) | Compte Django actif, profil consultable par le réseau. |
| `desinscription` | Désistement / Opt-out | 0 % (Lost) | L'alumni refuse de figurer dans l'annuaire public. |
