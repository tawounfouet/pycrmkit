---
name: freelance-mission-hunter
description: >
  Manage freelance developer mission hunting and applicant tracking (ATS) using PyCRMKit:
  track candidacies across platforms (Malt, LinkedIn, Freelance-Info, Direct), enforce J+5
  follow-ups, record interview logs, and compute funnel metrics (Win Rate, TJM, Weighted Revenue).
user-invocable: true
---

# Freelance Mission Hunter

Use this skill when prospecting, applying, and negotiating freelance missions during inter-contract periods, using PyCRMKit as a personal Applicant Tracking System (ATS).

* **Detailed Funnel Architecture & Stage Definitions** : [`workflow.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/freelance-mission-hunter/workflow.md)
* **Real-World Examples & CLI Recipes** : [`examples.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/freelance-mission-hunter/examples.md)

## Core Principles

1. **La Mission comme Opportunité B2B** : Une offre de mission est une `Opportunity` dont la valeur correspond à : $\text{TJM} \times \text{Durée en jours}$.
2. **Discipline de Relance à J+5** : Chaque candidature envoyée doit comporter une tâche de relance fixée impérativement à **J+5**.
3. **Pilotage par les KPIs** : Mesurer en temps réel le taux de conversion de chaque étape et le CA prévisionnel pondéré.

---

## Operating Workflows

### 1. Enregistrement d'une Nouvelle Offre Repérée

Dès qu'une annonce est repérée sur Malt, LinkedIn ou un site direct :

```bash
# 1. Création de l'entreprise (Client final ou ESN)
pck orgs create --name "<Entreprise / ESN>" --industry "<Secteur Tech>"

# 2. Création du contact (Recruteur RH ou CTO)
pck contacts create \
    --first-name "<Prénom>" \
    --last-name "<Nom>" \
    --email "<email@societe.com>"

# 3. Rattachement des métadonnées de l'offre
pck orgs update <org-id> \
    --custom "plateforme_source:<Malt / LinkedIn / Direct>" \
    --custom "tjm_demande:<ex: 650>" \
    --custom "modalite_remote:<Full Remote / Hybride>" \
    --custom "lien_offre:<URL de l'annonce>"
```

### 2. Candidature & Planification de la Relance

Après l'envoi du CV et de la proposition :

```bash
# 1. Avancement dans le pipeline de recrutement
pck sales move <deal-id> candidature_envoyee --pipeline freelance-job-hunt

# 2. Programmation obligatoire de la relance à J+5
pck tasks create \
    --title "Relance polie sur LinkedIn : <Nom du Recruteur> (<Nom Entreprise>)" \
    --priority HIGH \
    --due "<YYYY-MM-DD (Date aujourd'hui + 5 jours)>"
```

### 3. Gestion des Entretiens RH & Techniques

```bash
# Passage au screening RH ou test technique
pck sales move <deal-id> screening_rh --pipeline freelance-job-hunt
pck sales move <deal-id> entretien_tech --pipeline freelance-job-hunt

# Tâche de préparation avant le call
pck tasks create \
    --title "Préparer 3 questions d'architecture pour call CTO <Entreprise>" \
    --priority NORMAL \
    --due "<YYYY-MM-DD>"
```

Après l'entretien, consigner immédiatement les points clés dans la fiche contact :
```bash
pck contacts show <contact-id>
```

### 4. Clôture de la Mission

* **En cas de succès (Offre retenue)** :
  ```bash
  pck sales move <deal-id> won --pipeline freelance-job-hunt
  # Bascule vers le pipeline de delivery
  pck sales move <deal-id> specifications --pipeline agency-software-delivery
  ```
* **En cas de refus** :
  ```bash
  pck sales move <deal-id> lost --pipeline freelance-job-hunt
  # Tag pour réactiver le contact dans 6 mois
  pck contacts tag <contact-id> add "recontacter-futur"
  ```

---

## Analytics & KPIs de Recherche

Pour calculer vos statistiques consolidées de prospection :

```bash
# 1. Visualisation synthétique du pipeline et du CA pondéré
pck dashboard
```

Script Python pour extraire les performances par plateforme :
```python
from decimal import Decimal
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.facade.crm import CRM
from pycrmkit.opportunities import OpportunityStatus

crm = CRM()
opps = crm.opportunities.list(page=OffsetPageRequest(limit=100)).items

won = [o for o in opps if o.status == OpportunityStatus.WON]
total = len(opps)
win_rate = (len(won) / total * 100) if total > 0 else 0.0

print(f"🎯 Total Candidatures : {total} | 🏆 Gagnées : {len(won)} | Taux : {win_rate:.1f}%")
```
