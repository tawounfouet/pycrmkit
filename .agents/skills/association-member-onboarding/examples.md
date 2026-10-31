# Association Member Onboarding — Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Scripts SDK**  
> **Skill Associé** : [`association-member-onboarding`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/association-member-onboarding/SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/association-member-onboarding/workflow.md)  
> **Organisation de Référence** : Association *Diversité Alternative*

---

## Exemple 1 : Parcours d'Intégration Complet d'une Nouvelle Bénévole

### Profil de la Candidate :
- **Prénom & Nom** : Aminata Diallo
- **Origine** : Rencontrée au Gala Annuel 2026 (Billet HelloAsso n° `HA-GALA-2026-441`)
- **Cotisation** : 30 € réglée par virement bancaire
- **Pôle Souhaité** : Communication & Réseaux Sociaux

### 1. Ingestion Initiale post-Gala :
```bash
# 1. Création de la fiche contact
pck contacts create \
    --first-name "Aminata" \
    --last-name "Diallo" \
    --email "aminata.diallo.perso@yahoo.fr" \
    --phone "+33611223344"

# 2. Tag de promotion et d'événement
pck contacts update contact_aminata_diallo \
    --tags "event-gala-2026,promo-automne-2026,candidat-benevole"

# 3. Création de l'opportunité d'adhésion
pck sales opps create \
    --contact contact_aminata_diallo \
    --title "Adhésion 2026 - Aminata Diallo" \
    --pipeline adhesion-membres \
    --stage candidature_recue \
    --value 30
```

### 2. Entretien Découverte TA & Lettrage Trésorerie en Python :
```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()

contact_id = "contact_aminata_diallo"
opp_id = "opp_adhesion_aminata"

# A. Consignation de l'entretien dans la Timeline
crm.timeline.record_meeting(
    contact_id=contact_id,
    title="Entretien Découverte TA avec Aminata Diallo",
    description="Excellente aisance relationnelle. Expérience en community management TikTok et Instagram. Très bon fit avec l'équipe com.",
    actor_id="recruteur-ta-thomas",
)

# B. Avancement du stage après confirmation du virement par la Trésorerie
crm.pipelines.transition(
    opportunity_id=opp_id,
    target_stage="cotisation_validee",
    actor_id="tresoriere-sarah",
)

# C. Mise à jour des dates comptables de validité
crm.contacts.update_custom_fields(
    contact_id=contact_id,
    fields={
        "statut_adhesion": "adherent_actif",
        "canal_cotisation": "virement_bancaire",
        "montant_cotisation": 30,
        "date_adhesion": "2026-10-31",
        "date_expiration_adhesion": "2027-10-31",
        "pole_principal": "communication",
        "competences_cles": "Canva, Montage TikTok, Stratégie Instagram",
    },
)

# D. Création de la tâche IT pour l'administrateur Microsoft 365
ref = EntityReference("contact", contact_id)
crm.tasks.create(
    title="Créer UPN aminata.diallo@diversite-alternative.org + licence Teams",
    references=(ref,),
    priority="HIGH",
    due_date="2026-11-04",
)
```

### 3. Finalisation du Provisioning IT & Clôture :
```bash
# Renseignement de l'email officiel M365 et validation WhatsApp
pck contacts update contact_aminata_diallo \
    --custom "m365_upn:aminata.diallo@diversite-alternative.org" \
    --custom "m365_license_active:true" \
    --custom "whatsapp_joined:true"

# Clôture du parcours d'onboarding au statut Gagné
pck sales move opp_adhesion_aminata membre_actif --pipeline adhesion-membres
```

---

## Exemple 2 : Campagne de Renouvellement Annuel N+1

### Script de Relance Automatique des Adhérents à Échéance :
```python
# 1. Sélection automatique du segment des membres à renouveler ce mois
segment_echeance = crm.segments.create_dynamic(
    name="Adhérents à renouveler - Octobre 2027",
    filter_criteria={
        "statut_adhesion": "adherent_actif",
        "expiration_within_days": 30,
    },
)

# 2. Rattachement à la campagne de réadhésion v1.2.0
campagne_readhesion = crm.campaigns.create(
    key="readhesion-octobre-2027",
    name="Campagne de Réadhésion - Promotion 2026",
    status="active",
)
crm.campaigns.link_segment(
    campaign_id=campagne_readhesion.id,
    segment_id=segment_echeance.id,
)
```

En CLI :
```bash
pck campaigns audience readhesion-octobre-2027
```
