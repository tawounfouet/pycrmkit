---
name: association-member-onboarding
description: >
  Manage the complete non-profit member lifecycle, volunteer onboarding, and annual renewal
  for associations like Diversité Alternative using PyCRMKit: ingest event attendees (Eventbrite, HelloAsso),
  process Talent Acquisition discovery calls, reconcile multi-channel membership dues (HelloAsso,
  bank transfer, PayPal), automate Microsoft 365 and WhatsApp community onboarding tasks, and run
  annual N+1 membership renewal campaigns.
user-invocable: true
---

# Association Member Onboarding & Retention (`association-member-onboarding`)

Use this skill when managing the volunteer recruitment funnel, membership fees, IT account provisioning, and annual renewals for non-profit organizations and associations (specifically tailored for **Diversité Alternative**).

* **Detailed Funnel Architecture & Multi-Team Workflow** : [`workflow.md`](workflow.md)
* **Real-World Examples & CLI Recipes** : [`examples.md`](examples.md)

---

## Core Rules

1. **La Fiche Unique Omnicanale** : Chaque participant à un événement et chaque candidat possède une fiche contact unique réconciliant ses identifiants tiers (`eventbrite:ticket_id`, `helloasso:order_id`, `microsoft:upn`).
2. **La Règle du Double Formulaire** :
   - **Forms 1 (Candidature)** : déclenche immédiatement l'opportunité au stage `candidature_recue` pour la team Talent Acquisition (TA).
   - **Forms 2 (Annuaire & Compétences)** : complété post-paiement, il alimente les Custom Fields de l'annuaire et génère la tâche IT.
3. **Traçabilité du Call de Découverte** : Tout entretien TA individuel doit être consigné dans la `crm.timeline` du candidat avant de lui transmettre les coordonnées de cotisation.
4. **Pointage Trésorerie Déterminé** : Valider systématiquement le canal de paiement (`helloasso_cb`, `virement_bancaire`, `paypal`) et fixer `date_expiration_adhesion = date_paiement + 365 jours`.
5. **Génération Systématique de la Tâche IT** : Dès validation du paiement, créer une tâche d'assignation prioritaire `HIGH` pour la création du compte Microsoft 365 (`prenom.nom@diversite-alternative.org`).
6. **Relance Réadhésion à J-30** : Surveiller automatiquement l'échéance annuelle pour intégrer les membres expirant dans le segment dynamique de réadhésion N+1.

---

## Operating Workflows

### 1. Ingestion des Inscrits d'Événements & Candidature (Forms 1)

Dès qu'un événement s'achève et qu'un participant soumet le Formulaire 1 de manifestation d'intérêt :

```bash
# 1. Création ou mise à jour de la fiche contact
pck contacts create \
    --first-name "Khadija" \
    --last-name "Benali" \
    --email "khadija.benali.perso@gmail.com" \
    --phone "+33698765432"

# 2. Rattachement du tag de l'événement et du statut
pck contacts update <contact-id> \
    --tags "event-gala-2026,promo-printemps-2026,candidat-benevole"

# 3. Création de l'opportunité dans le pipeline associatif
pck sales opps create \
    --contact <contact-id> \
    --title "Adhésion Bénévole 2026 - Khadija Benali" \
    --pipeline "adhesion-membres" \
    --stage "candidature_recue" \
    --value 30
```

---

### 2. Conduite du Call Découverte & Qualification TA

L'équipe Talent Acquisition mène l'entretien individuel de 30 minutes :

```python
from pycrmkit import CRM

crm = CRM.memory()  # ou persistance PostgreSQL locale

contact_id = "..."  # ID du contact Khadija Benali
opp_id = "..."      # ID de l'opportunité d'adhésion

# 1. Consignation du compte-rendu d'entretien dans la Timeline
crm.timeline.record_meeting(
    contact_id=contact_id,
    title="Call Découverte TA avec Khadija Benali",
    description="Très motivée pour le pôle Événementiel et partenariats. Expérience passée en gestion de projets. Entretien validé à l'unanimité.",
    actor_id="recruteur-ta-thomas",
)

# 2. Avancement au stage Attente Cotisation
crm.pipelines.transition(
    opportunity_id=opp_id,
    target_stage="cotisation_attente",
    actor_id="recruteur-ta-thomas",
)
```

En ligne de commande CLI :
```bash
pck sales move <opp-id> cotisation_attente --pipeline adhesion-membres
```

---

### 3. Rapprochement Trésorerie Multi-Canal (HelloAsso / Virement / PayPal)

Dès réception du règlement de la cotisation annuelle :

```bash
# 1. Validation de l'étape financière
pck sales move <opp-id> cotisation_validee --pipeline adhesion-membres

# 2. Enregistrement des données comptables sur la fiche adhérent
pck contacts update <contact-id> \
    --custom "statut_adhesion:adherent_actif" \
    --custom "canal_cotisation:helloasso_cb" \
    --custom "montant_cotisation:30" \
    --custom "date_adhesion:2026-10-31" \
    --custom "date_expiration_adhesion:2027-10-31"
```

---

### 4. Enrichissement Forms 2 & Provisioning IT (Microsoft 365 + WhatsApp)

Dès que le nouveau membre a complété le Formulaire 2 (annuaire, compétences et disponibilités) :

```python
from pycrmkit.core.references import EntityReference

# 1. Enrichissement des compétences et affectation de pôle
crm.contacts.update_custom_fields(
    contact_id=contact_id,
    fields={
        "pole_principal": "evenementiel",
        "competences_cles": "Gestion de budget, Négociation prestataires, Logistique salon",
        "linkedin_url": "https://linkedin.com/in/khadija-benali",
    },
)

# 2. Création de la tâche prioritaire pour l'administrateur Microsoft 365
ref = EntityReference("contact", contact_id)
crm.tasks.create(
    title="Provisioning M365 : khadija.benali@diversite-alternative.org + Groupes WhatsApp",
    references=(ref,),
    priority="HIGH",
    due_date="2026-11-03",
)
```

Une fois le compte créé par l'IT :
```bash
pck contacts update <contact-id> \
    --custom "m365_upn:khadija.benali@diversite-alternative.org" \
    --custom "m365_license_active:true" \
    --custom "whatsapp_joined:true"

# Clôture finale de l'onboarding au stage Won
pck sales move <opp-id> membre_actif --pipeline adhesion-membres
```

---

### 5. Surveillance & Campagne Annuelle de Renouvellement (N+1)

Chaque mois, la Trésorerie identifie les membres dont la cotisation arrive à échéance :

```python
# 1. Détection des adhérents arrivant à échéance sous 30 jours
segment_readhesion = crm.segments.create_dynamic(
    name="Adhérents à renouveler ce mois-ci",
    filter_criteria={
        "statut_adhesion": "adherent_actif",
        "expiration_within_days": 30,
    },
)

# 2. Création de la campagne d'emailing de réadhésion (v1.2.0)
campagne = crm.campaigns.create(
    key="campagne-readhesion-2027",
    name="Campagne de Réadhésion Promotion 2026",
    status="active",
)
crm.campaigns.link_segment(campaign_id=campagne.id, segment_id=segment_readhesion.id)
```

En CLI pour visualiser les métriques de la campagne :
```bash
pck campaigns audience campagne-readhesion-2027
```

---

## Checklist de Contrôle Qualité

Avant de clôturer une intégration d'adhérent dans l'association, vérifier :

- [ ] Identifiant de billetterie Eventbrite ou HelloAsso consigné dans les `ExternalIdentities`.
- [ ] Compte-rendu du call de découverte enregistré dans la `Timeline`.
- [ ] Canal de cotisation (`helloasso_cb`, `virement_bancaire`, `paypal`) et montant renseignés.
- [ ] Date d'expiration de l'adhésion (`date_expiration_adhesion`) calculée à date + 365 jours.
- [ ] Tâche IT Microsoft 365 exécutée et UPN (`@diversite-alternative.org`) renseigné.
- [ ] Confirmation d'ajout dans les groupes WhatsApp officiels (Général + Pôle).
- [ ] Statut de l'opportunité passé à `membre_actif` (*Closed Won*).
