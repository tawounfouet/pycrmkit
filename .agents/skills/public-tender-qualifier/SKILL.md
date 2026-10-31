---
name: public-tender-qualifier
description: >
  Qualify and manage public procurement tenders (marchés publics, MAPA, accords-cadres)
  using PyCRMKit: enforce Go/No-Go criteria, lock J-1 DLRO submission deadlines,
  manage consortium partnerships (GME cotraitance), and record post-verdict debriefings.
user-invocable: true
---

# Public Tender Qualifier & Bid Manager

Use this skill when analyzing, preparing, and tracking public procurement tenders (appels d'offres, MAPA, accords-cadres de l'État ou des collectivités) with PyCRMKit.

* **Detailed Procurement Lifecycle & Go/No-Go Scorecard** : [`workflow.md`](workflow.md)
* **Real-World Examples & CLI Recipes** : [`examples.md`](examples.md)

## Core Rules & Invariants

1. **Règle d'Or DLRO à J-1 (16h00)** : La date limite de remise des plis (DLRO) est éliminatoire à la seconde près. La tâche de dépôt officiel **doit impérativement être fixée à J-1, 16h00**, avec la priorité `URGENT`.
2. **Go / No-Go Préalable** : Ne jamais engager la rédaction d'un mémoire technique sans valider formellement la qualification technique, la rentabilité financière et la pondération des critères.
3. **Capitalisation des Débriefings** : Chaque notification de rejet ou d'attribution doit être accompagnée de l'archivage de la grille de notation détaillée (note technique et note prix).

---

## Operating Workflows

### 1. Ingestion de l'Avis de Marché

Lorsqu'un avis est repéré sur le BOAMP, PLACE ou un profil d'acheteur :

```bash
# 1. Création de l'acheteur public
pck orgs create \
    --name "<Collectivité / Ministère / Université>" \
    --industry "Secteur Public"

# 2. Création du contact prescripteur ou acheteur
pck contacts create \
    --first-name "<Prénom>" \
    --last-name "<Nom>" \
    --email "<email@acheteur-public.fr>"

# 3. Rattachement des métadonnées du marché
pck orgs update <org-id> \
    --custom "numero_marche:<ex: 2026-MAPA-042>" \
    --custom "type_procedure:<MAPA / AO Ouvert / Accord-Cadre>" \
    --custom "dlro_datetime:<YYYY-MM-DD HH:MM>" \
    --custom "plateforme_depot:<PLACE / AWS / Maximilien>"
```

### 2. Décision Go / No-Go

Évaluer l'opportunité selon 4 critères éliminatoires :
* Compétence technique sur 90% du CCTP ?
* Poids du prix inférieur ou égal à 60% ?
* Calendrier de livraison réaliste ?
* Marge prévisionnelle suffisante ?

* **Si GO** :
  ```bash
  # Passage en rédaction de réponse
  pck sales move <deal-id> redaction_reponse --pipeline public-tenders-bid-management

  # Verrouillage impératif du dépôt à J-1
  pck tasks create \
      --title "[DLRO J-1] Dépôt Pli Dématérialisé <Nom du Marché>" \
      --priority URGENT \
      --due "<YYYY-MM-DD (Veille de la DLRO à 16h00)>"
  ```
* **Si NO-GO** :
  ```bash
  pck sales move <deal-id> lost --pipeline public-tenders-bid-management
  ```

### 3. Gestion des Groupements Momentanés d'Entreprises (Cotraitance GME)

Si la réponse nécessite une alliance avec un partenaire (designer UI/UX, auditeur accessibilité RGAA, hébergeur) :

```python
from pycrmkit.core.references import EntityReference
from pycrmkit.facade.crm import CRM

crm = CRM()
# Enregistrer le partenariat de cotraitance
crm.relationships.create(
    source=EntityReference("organization", org_agence.id),
    target=EntityReference("organization", org_partenaire.id),
    relationship_type="gme_partner",
    role="Cotraitant UI/UX & Design System",
    metadata={"quote_part": "35%", "convention_signee": True}
)
```

### 4. Dépôt Sécurisé et Clôture

```bash
# Une fois le pli déposé et l'accusé de réception horodaté obtenu :
pck sales move <deal-id> depot_securise --pipeline public-tenders-bid-management

# Lors de la notification d'attribution :
# Si Gagné :
pck sales move <deal-id> won --pipeline public-tenders-bid-management
pck sales move <deal-id> specifications --pipeline agency-software-delivery

# Si Rejeté : consigner la note pour progresser
pck sales move <deal-id> lost --pipeline public-tenders-bid-management
pck orgs update <org-id> \
    --custom "note_technique:54" \
    --custom "note_prix:28" \
    --custom "classement_final:2"
```

---

## Verification Commands

Pour inspecter les échéances publiques imminentes :
```bash
# Vérifier les tâches urgentes du calendrier de dépôt
pck tasks list

# Tableau de bord global
pck dashboard
```
