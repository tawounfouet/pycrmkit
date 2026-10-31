# Agency Client Lifecycle - Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Scripts SDK**  
> **Skill Associé** : [`agency-client-lifecycle`](SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](workflow.md)

---

## Exemple 1 : Devis Gagné et Bascule vers le Delivery Logiciel

### Scénario :
Le client **Airbus Defense & Space** a signé un devis de 220 000 € HT pour la refonte de son portail de télémétrie spatiale. L'acompte de 30 % (66 000 €) vient d'être reçu sur le compte bancaire.

### 1. Clôture de l'Affaire Commerciale en CLI :
```bash
# 1. Passage de l'opportunité au statut Gagné
pck sales move deal_airbus_telemetry won --pipeline agency-commercial

# 2. Ajout du tag client et statut de contrat
pck orgs update org_airbus_ds \
    --tags "client-actif,contrat-signe,tier-1"

# 3. Initialisation de l'affaire de delivery
pck sales opps create \
    --org org_airbus_ds \
    --title "Delivery : Portail Télémétrie Spatiale v1.0" \
    --pipeline agency-software-delivery \
    --stage kickoff \
    --value 220000
```

### 2. Configuration des Métadonnées Techniques en Python :
```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()  # ou persistance PostgreSQL

org_id = "..."      # ID de Airbus DS
contact_id = "..."  # ID du Lead Architecte

# Enregistrement des Custom Fields du projet
crm.organizations.update_custom_fields(
    org_id=org_id,
    fields={
        "tech_stack": "FastAPI, PostgreSQL 17, React 19, Kubernetes",
        "repo_url": "git@github.com:airbus-ds/telemetry-portal.git",
        "url_staging": "https://staging.telemetry.airbus-ds.internal",
        "url_production": "https://telemetry.airbus-ds.internal",
    },
)

# Tâche de cadrage pour l'équipe technique
ref = EntityReference("organization", org_id)
crm.tasks.create(
    title="Animer atelier Kickoff & livrer environnement Staging",
    references=(ref,),
    priority="HIGH",
    due_date="2026-11-06",
)
```

---

## Exemple 2 : Gestion d'un Forfait MCO & Ticket d'Urgence

### Scénario :
Le client **Institut Curie Technologies** souscrit un forfait MCO de 20 heures/mois avec un niveau SLA VIP (GTI 2h). Une anomalie de paiement en ligne est signalée sur leur plateforme.

### 1. Déclaration du contrat MCO :
```bash
# Configuration du contrat MCO sur l'organisation
pck orgs update org_curie_tech \
    --tags "mco-actif,sla-vip" \
    --custom "mco_sla_level:vip" \
    --custom "mco_monthly_hours:20" \
    --custom "mco_consumed_hours:0"
```

### 2. Réception et Traitement de l'Incident :
```python
# 1. Enregistrement de l'incident dans la timeline du client
crm.timeline.record_incident(
    organization_id="org_curie_tech",
    title="Incident P1 : Blocage webhook Stripe checkout",
    severity="CRITICAL",
    actor_id="dev-support-thomas",
    description="Erreur 500 sur le point de terminaison webhook suite à une mise à jour de certificat SSL.",
)

# 2. Création de la tâche de résolution immédiate
ref_org = EntityReference("organization", "org_curie_tech")
crm.tasks.create(
    title="Résoudre certificat SSL webhook Stripe (GTI 2h)",
    references=(ref_org,),
    priority="URGENT",
    due_date="2026-10-31",
)

# 3. Après résolution : Décompte de 2 heures d'intervention
crm.organizations.update_custom_fields(
    org_id="org_curie_tech",
    fields={
        "mco_consumed_hours": 2,
    },
)
```
