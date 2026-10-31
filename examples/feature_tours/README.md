# PyCRMKit Feature Tours Suite

Ce dossier contient une suite complète de scripts Python autonomes et exécutables pour explorer et tester l'intégralité des fonctionnalités de **PyCRMKit 1.2.0**.

Chaque script s'exécute en mémoire (`CRM.memory()`), sans dépendance externe ou serveur requis, et valide ses assertions de manière déterministe.

---

## 📋 Inventaire des Scripts

| Script | Domaine Fonctionnel | Fonctionnalités Clés Testées |
|---|---|---|
| [`01_core_crm.py`](./01_core_crm.py) | **Fondations CRM** | Organisations, Contacts (emails/phones typés), Relations n-aire, Tags avec `EntityReference`, Champs personnalisés avec validation de type. |
| [`02_sales_pipelines.py`](./02_sales_pipelines.py) | **Pipelines & Ventes** | Définition de pipeline avec probabilités par étape, opportunités monétaires, transitions d'étape (`crm.opportunities.move`), conversion Deal -> Won, calcul de pondération. |
| [`03_events_and_webhooks.py`](./03_events_and_webhooks.py) | **Événements & Webhooks** | Abonnement EventBus (`crm.events`), capture des métadonnées d'acteur et corrélation, abonnements Webhook (`crm.webhooks`), signature HMAC, rotation de secret, envoi d'email avec mock. |
| [`04_data_operations.py`](./04_data_operations.py) | **Qualité & DataOps** | Ingestion CSV via `CSVReader`, détection de doublons avec `DeduplicationEngine` et règles exactes/fuzzy, garde anti-injection tableur (`prevent_spreadsheet_injection`). |
| [`05_segmentation_queries.py`](./05_segmentation_queries.py) | **Segmentation & Requêtes** | Segments statiques avec appartenance manuelle, segments dynamiques avec prédicats (`Predicate`, `QueryOperator.EQ`), snapshots figés d'audience résistant aux mutations. |
| [`06_campaigns_v1_2.py`](./06_campaigns_v1_2.py) | **Campagnes v1.2.0 & Attribution** | Concurrence optimiste (`expected_revision`, `ConflictError`), membres directs, capture de sources de segments, résolution d'audience dédupliquée, liaison de touchpoints sans fuite du corps, export JSONL paginé, cycle de vie (activation / complétion). |
| [`run_all_tours.py`](./run_all_tours.py) | **Orchestrateur Global** | Exécute séquentiellement les 6 tours, mesure les temps d'exécution et génère le tableau récapitulatif consolidé. |

---

## 🚀 Utilisation

### Exécuter un tour individuel
```bash
python3 examples/feature_tours/01_core_crm.py
python3 examples/feature_tours/02_sales_pipelines.py
python3 examples/feature_tours/03_events_and_webhooks.py
python3 examples/feature_tours/04_data_operations.py
python3 examples/feature_tours/05_segmentation_queries.py
python3 examples/feature_tours/06_campaigns_v1_2.py
```

### Exécuter la suite complète
```bash
python3 examples/feature_tours/run_all_tours.py
```
