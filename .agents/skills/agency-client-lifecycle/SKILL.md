---
name: agency-client-lifecycle
description: >
  Manage end-to-end web agency and solo developer client relationships using PyCRMKit:
  from commercial proposal, lead qualification, and conversion to dual-pipeline delivery
  (software realization) and ongoing MCO maintenance contracts with SLA and tasks.
user-invocable: true
---

# Agency Client Lifecycle

Use this skill when managing the full commercial, delivery, and maintenance lifecycle of a web agency or solo software studio using PyCRMKit.

## Core Capabilities

1. **Avant-Vente & Devis** : Ingestion de leads entrants, qualification, conversion atomique en `Organization` + `Contact` + `Opportunity`, et suivi du pipeline commercial.
2. **Delivery Logiciel** : Bascule du deal gagné dans le pipeline `agency-software-delivery`, stockage des métadonnées techniques (repo Git, URL staging/prod, stack) via les `custom_fields`.
3. **MCO & Maintenance** : Configuration des forfaits d'heures mensuels, niveaux de SLA (GTI/GTR), tags de statut (`#mco-actif`, `#support-vip`) et planification des audits périodiques.

---

## Step-by-Step Procedures

### 1. Ingestion et Conversion du Prospect

Lorsqu'un prospect prend contact pour un projet web ou logiciel :

```bash
# 1. Création du lead qualifié
pck leads create \
    --name "<Nom du Contact>" \
    --org "<Nom de l'Entreprise>" \
    --email "<email@entreprise.com>" \
    --phone "<+336XXXXXXXX>" \
    --source "inbound_web"

# 2. Conversion atomique en Compte + Contact + Affaire
pck leads convert <lead-id> \
    --deal-name "Projet <Nom du Projet>" \
    --amount <Montant HT en EUR> \
    --currency EUR
```

### 2. Négociation & Clôture Commerciale

Suivre l'opportunité dans le pipeline commercial jusqu'à la signature :

```bash
# Visualiser les opportunités en cours
pck sales opps

# Déplacer l'opportunité selon l'avancement
pck sales move <deal-id> devis_envoye
pck sales move <deal-id> won

# Programmer la tâche d'acompte
pck tasks create \
    --title "Vérifier réception acompte 30% et signer devis" \
    --priority HIGH \
    --due "<YYYY-MM-DD>"
```

### 3. Lancement du Delivery Logiciel

Une fois l'affaire gagnée (`won`), basculer dans le pipeline de réalisation :

```bash
# 1. Déplacement dans le pipeline de delivery
pck sales move <deal-id> sprint_dev --pipeline agency-software-delivery

# 2. Renseignement des métadonnées techniques sur l'organisation
pck orgs update <org-id> \
    --custom "repo_git:https://github.com/mon-agence/<projet>" \
    --custom "url_staging:https://staging.<projet>.dev" \
    --custom "stack_technique:Django / React / PostgreSQL"

# 3. Programmation du jalon de recette
pck tasks create \
    --title "Démo de validation sur environnement Staging" \
    --entity-id <org-id> \
    --priority HIGH \
    --due "<YYYY-MM-DD>"
```

### 4. Activation du MCO Post-Livraison

Après la mise en production et la signature du PV de recette :

```bash
# 1. Attribution des tags de maintenance
pck orgs tag <org-id> add "mco-actif" "support-vip"

# 2. Renseignement du contrat de maintenance
pck orgs update <org-id> \
    --custom "mco_forfait:8h / mois" \
    --custom "mco_taux_horaire:90 EUR/h" \
    --custom "mco_sla:GTI 4h ouvrées" \
    --custom "mco_date_anniversaire:<YYYY-MM-DD>"

# 3. Programmation de la première maintenance préventive
pck tasks create \
    --title "[MCO] Audit sécurité mensuel & mise à jour dépendances" \
    --entity-id <org-id> \
    --priority NORMAL \
    --due "<YYYY-MM-DD>"
```

---

## SDK Python Reference

Pour initialiser automatiquement l'environnement d'une agence en Python :

```python
from pycrmkit.facade.crm import CRM

crm = CRM()

# 1. Pipelines
sales_pipe = crm.pipelines.create(
    name="Agence - Vente",
    stages=["qualification", "cadrage_technique", "devis_envoye", "negociation", "won", "lost"]
)
delivery_pipe = crm.pipelines.create(
    name="agency-software-delivery",
    stages=["specifications", "sprint_dev", "recette_staging", "mise_en_prod", "recette_definitive"]
)

# 2. Custom Fields d'Agence
crm.custom_fields.define(entity_kind="organization", name="repo_git", field_type="string")
crm.custom_fields.define(entity_kind="organization", name="url_staging", field_type="string")
crm.custom_fields.define(entity_kind="organization", name="mco_forfait", field_type="string")
crm.custom_fields.define(entity_kind="organization", name="mco_sla", field_type="string")

# 3. Tags d'Agence
crm.tags.create(name="mco-actif", color="#10B981")
crm.tags.create(name="support-vip", color="#F59E0B")
```

---

## Verification Commands

Pour valider l'état global et vérifier qu'aucun jalon ou contrat n'est en souffrance :
```bash
# 1. Cockpit de pilotage exécutif (KPIs, CA prévisionnel, relances)
pck dashboard

# 2. Consultation de la fiche 360° du client
pck orgs show <org-id>
```
