---
name: student-career-launch
description: >
  Guide students, apprentices, and junior developers in tracking job hunts for internships,
  alternances, and junior CDD/CDI positions using PyCRMKit: track applications across
  platforms (WTTJ, LinkedIn, JobTeaser), enforce polite J+5 follow-ups, prepare interview
  briefs, and generate academic search reports.
user-invocable: true
---

# Student Career Launch & ATS

Use this skill when managing the job search for internships (stages), work-study programs (alternances), or early-career CDD/CDI positions with PyCRMKit.

## Core Rules

1. **La Fiche Prête en 2 Secondes** : Chaque entreprise ciblée doit avoir une fiche prête dans le CRM pour répondre immédiatement sans bégayer lors d'un appel impromptu d'un recruteur.
2. **Relance Polie à J+5** : Ne jamais laisser un CV mourir sous la pile. Programmer systématiquement une relance courtoise sur LinkedIn ou par email à **J+5**.
3. **Le « Meta-Projet »** : Utiliser la méthode de recherche et le CRM comme argument d'entretien pour prouver sa rigueur de futur développeur.

---

## Operating Workflows

### 1. Enregistrement d'une Candidature

Dès qu'une offre intéressante est repérée (Welcome to the Jungle, LinkedIn, JobTeaser) :

```bash
# 1. Création de l'entreprise
pck orgs create --name "<Nom Entreprise / Startup>" --industry "<Secteur>"

# 2. Création du recruteur RH ou Campus Manager
pck contacts create \
    --first-name "<Prénom>" \
    --last-name "<Nom>" \
    --email "<email@societe.com>"

# 3. Rattachement des spécificités scolaires
pck orgs update <org-id> \
    --custom "type_contrat:<Stage 6 mois / Alternance 12 mois / CDI Junior>" \
    --custom "rythme_scolaire:<ex: 3 sem entreprise / 1 sem école>" \
    --custom "remuneration:<ex: 1400 EUR/mois>" \
    --custom "stack_demandee:<Python, Django, React, Docker>"
```

### 2. Candidature & Programmation de la Relance

```bash
# 1. Avancement dans le pipeline étudiant
pck sales move <deal-id> candidature_envoyee --pipeline student-career-launch

# 2. Programmation obligatoire de la relance polie à J+5
pck tasks create \
    --title "Relance polie sur LinkedIn : <Prénom Nom Recruteur> (<Entreprise>)" \
    --priority HIGH \
    --due "<YYYY-MM-DD (Date du jour + 5 jours)>"
```

### 3. Gestion du Test Technique & Préparation d'Entretien

```bash
# Déplacement lors de la réception du test
pck sales move <deal-id> test_technique --pipeline student-career-launch

# Deadline stricte de rendu du test
pck tasks create \
    --title "Rendu repo GitHub test technique <Entreprise>" \
    --priority URGENT \
    --due "<YYYY-MM-DD>"
```

Consigner les questions posées et les axes d'amélioration après chaque entretien :
```bash
pck contacts show <contact-id>
```

### 4. Clôture & Signature de Convention / Contrat

```bash
# Quand l'offre est confirmée par l'entreprise :
pck sales move <deal-id> won --pipeline student-career-launch

# Tag de concrétisation
pck orgs tag <org-id> add "alternance-validee" "promotion-2026"
```

---

## Outputting Academic Reports

Pour justifier ses démarches auprès du responsable des stages de l'école ou de l'université :

```python
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.facade.crm import CRM

crm = CRM()
opps = crm.opportunities.list(page=OffsetPageRequest(limit=100)).items

print("📋 Rapport d'Effort de Recherche d'Alternance / Stage :")
for o in opps:
    print(f"• {o.title:<35} | Étape : {o.stage_id:<20} | Statut : {o.status.value}")
```
