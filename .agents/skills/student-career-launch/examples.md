# Student Career Launch — Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Scripts SDK**  
> **Skill Associé** : [`student-career-launch`](SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](workflow.md)

---

## Exemple 1 : Candidature Alternance chez Doctolib

### Contexte :
L'étudiant postule pour une alternance de 12 mois (rythme 3 semaines entreprise / 1 semaine école) chez **Doctolib**.  
- **Recruteur Campus** : Maxime Leroy
- **Stack** : Ruby on Rails, React, TypeScript, PostgreSQL

### 1. Enregistrement de la Fiche en CLI :
```bash
# 1. Création de l'entreprise
pck orgs create --name "Doctolib" --industry "HealthTech"

# 2. Création du contact Campus Manager
pck contacts create \
    --first-name "Maxime" \
    --last-name "Leroy" \
    --email "maxime.leroy@doctolib.com"

# 3. Création de l'opportunité d'alternance
pck sales opps create \
    --title "Alternance Développeur Full-Stack (12 mois)" \
    --value 18000 \
    --pipeline student-career-launch \
    --stage candidature_envoyee

# 4. Tâche de relance obligatoire à J+5
pck tasks create \
    --title "Relancer Maxime Leroy sur LinkedIn (J+5 candidature Doctolib)" \
    --priority HIGH \
    --due "2026-11-05"
```

---

## Exemple 2 : Préparation du Test Technique & Consignation de l'Entretien

### Script Python pour préparer l'entretien :
```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()

contact_id = "contact_maxime_leroy"
opp_id = "opp_doctolib_alternance"

# 1. Enregistrement du debrief du premier entretien RH
crm.timeline.record_meeting(
    contact_id=contact_id,
    title="Entretien RH Visio avec Maxime Leroy (30 min)",
    description=(
        "Entretien très fluide. Présentation de mon projet PyCRMKit qui a beaucoup plu ! "
        "Questions sur la gestion de la concurrence et l'architecture hexagonale. "
        "Étape suivante : Test technique kata d'algorithmique à rendre avant le 10 Novembre."
    ),
    actor_id="etudiant-dev",
)

# 2. Avancement au stage Test Technique
crm.pipelines.transition(
    opportunity_id=opp_id,
    target_stage="test_technique",
    actor_id="etudiant-dev",
)

# 3. Tâche de rendu du test technique
ref = EntityReference("opportunity", opp_id)
crm.tasks.create(
    title="Finaliser et livrer le test technique GitHub pour Doctolib",
    references=(ref,),
    priority="URGENT",
    due_date="2026-11-09",
)
```

---

## Exemple 3 : Export du Bilan de Recherche pour l'École

Pour attester de ses démarches auprès de son université ou de son école d'ingénieurs :
```bash
# Lister toutes les opportunités et leur état
pck sales opps --pipeline student-career-launch

# Exporter le rapport d'activité
pck dashboard
```
