# Freelance Mission Hunter — Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Scripts SDK**  
> **Skill Associé** : [`freelance-mission-hunter`](SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](workflow.md)

---

## Exemple 1 : Du Sourcing sur Malt à l'Entretien Technique

### Contexte :
Une offre de Lead Dev Python / FastApi en full-remote pour une FinTech parisienne est repérée sur Malt.  
- **Client** : FinTech Horizon SAS
- **Contact Recruteur** : Sophie Morand (Head of Talent)
- **TJM Proposé** : 700 € / jour
- **Durée** : 6 mois renouvelables (120 jours = 84 000 € HT)

### 1. Enregistrement en Ligne de Commande :
```bash
# 1. Création de l'entreprise cliente
pck orgs create --name "FinTech Horizon SAS" --industry "FinTech / Banking"

# 2. Création du contact Talent
pck contacts create \
    --first-name "Sophie" \
    --last-name "Morand" \
    --email "sophie.morand@horizon-fintech.io"

# 3. Création de l'opportunité de mission
pck sales opps create \
    --title "Mission Lead Dev Python / FastAPI (6 mois)" \
    --value 84000 \
    --pipeline freelance-job-hunt \
    --stage offre_reperee

# 4. Envoi de la candidature et programmation de la relance J+5
pck sales move opp_fintech_horizon candidature_envoyee --pipeline freelance-job-hunt

pck tasks create \
    --title "Relancer Sophie Morand sur LinkedIn (J+5 candidature envoyée)" \
    --priority HIGH \
    --due "2026-11-05"
```

---

## Exemple 2 : Débriefing d'Entretien Technique & Négociation TJM

### Script Python d'Enregistrement de l'Entretien :
```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()

contact_id = "contact_sophie_morand"
opp_id = "opp_fintech_horizon"

# 1. Enregistrement des notes de l'entretien technique avec le CTO
crm.timeline.record_meeting(
    contact_id=contact_id,
    title="Entretien Technique avec Alexandre (CTO)",
    description=(
        "Questions sur l'optimisation des requêtes PostgreSQL, architecture hexagonale et DDD. "
        "Excellent feeling technique. Le CTO valide la mission et propose un démarrage le 15 Novembre. "
        "Négociation TJM en cours : proposé 680 €, contre-proposition envoyée à 700 €."
    ),
    actor_id="freelance-thomas",
)

# 2. Avancement au stage Proposition TJM (90%)
crm.pipelines.transition(
    opportunity_id=opp_id,
    target_stage="proposition_tjm",
    actor_id="freelance-thomas",
)

# 3. Tâche de revue du bon de commande (BdC)
ref = EntityReference("opportunity", opp_id)
crm.tasks.create(
    title="Relire et signer le bon de commande envoyé par Malt",
    references=(ref,),
    priority="URGENT",
    due_date="2026-11-08",
)
```

### 3. Consultation du Tableau de Bord des Chasses en cours :
```bash
pck dashboard
```
Le dashboard affiche immédiatement le TJM moyen, le revenu pondéré et les relances planifiées.
