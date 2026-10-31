# Public Tender Qualifier — Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Scripts SDK**  
> **Skill Associé** : [`public-tender-qualifier`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/public-tender-qualifier/SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/public-tender-qualifier/workflow.md)

---

## Exemple 1 : Réponse à un Marché Public (MAPA) pour une Région

### Contexte :
La **Région Île-de-France** lance un MAPA pour le développement d'un portail open-data à destination des tiers-lieux.  
- **Numéro du Marché** : `2026-MAPA-IDF-089`
- **DLRO Officielle** : 2026-11-20 à 12h00
- **Verrou DLRO J-1** : 2026-11-19 à 16h00 (Obligatoire !)
- **Estimation Montant** : 75 000 € HT

### 1. Ingestion de l'Acheteur & de l'Affaire :
```bash
# 1. Création de l'entité publique
pck orgs create \
    --name "Région Île-de-France" \
    --industry "Collectivité Territoriale"

# 2. Rattachement du contact acheteur / prescripteur
pck contacts create \
    --first-name "Guillaume" \
    --last-name "Perrin" \
    --email "guillaume.perrin@iledefrance.fr"

# 3. Création de l'opportunité dans le pipeline marché public
pck sales opps create \
    --title "Marché 2026-MAPA-IDF-089 : Portail Open-Data Tiers-Lieux" \
    --value 75000 \
    --pipeline public-tenders-bid-management \
    --stage veille_dce
```

### 2. Validation Go / No-Go & Verrouillage DLRO en Python :
```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()

opp_id = "opp_mapa_idf_089"

# 1. Enregistrement de l'évaluation Go/No-Go dans la timeline
crm.timeline.record_note(
    opportunity_id=opp_id,
    title="Évaluation Go/No-Go : Validé (Score 88/100)",
    actor_id="directeur-technique",
    content=(
        "CCTP 100% maîtrisé (Python, PostgreSQL, CKAN). "
        "Pondération : 60% technique, 40% prix. "
        "DLRO dans 20 jours. Décision : GO franc."
    ),
)

# 2. Avancement de stage vers la rédaction
crm.pipelines.transition(
    opportunity_id=opp_id,
    target_stage="redaction_reponse",
    actor_id="directeur-technique",
)

# 3. Création du Verrou DLRO à J-1 (16h00)
ref_opp = EntityReference("opportunity", opp_id)
crm.tasks.create(
    title="[VERROU DLRO J-1] Dépôt ferme du pli sur PLACE pour Marché IDF-089",
    references=(ref_opp,),
    priority="URGENT",
    due_date="2026-11-19 16:00",
)
```

---

## Exemple 2 : Débriefing & Capitalisation REX post-verdict

### Cas d'un dossier Rejeté avec demande de Grille de Notation :
```python
# Consignation du débriefing de rejet pour capitalisation d'équipe
crm.timeline.record_note(
    opportunity_id=opp_id,
    title="Débriefing Rejet Acheteur Public - REX 2026-MAPA-IDF-089",
    actor_id="commercial-ao",
    content=(
        "Attribué au concurrent Atos. "
        "Notes obtenues : Technique 54/60 (Classé 1er en tech !) | Prix 28/40 (offre plus chère de 12%). "
        "Enseignement REX : Notre mémoire technique est excellent ; ajuster le taux journalier de 5% sur le prochain lot."
    ),
)

# Clôture au stage offre_rejetee
crm.pipelines.transition(
    opportunity_id=opp_id,
    target_stage="offre_rejetee",
    actor_id="commercial-ao",
)
```
