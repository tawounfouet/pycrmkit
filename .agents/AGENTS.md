# PyCRMKit Agentic Ecosystem — Orchestration des Agents Autonomes

> **Manifeste de l'Architecture Agentique de PyCRMKit**  
> **Localisation** : `professionnal/webtech/packages/pycrmkit/.agents/`  
> **Socle Exécutable** : CLI `pck` + Facades Python de PyCRMKit (v1.2.0+)  
> **Version de l'Écosystème** : 1.0.0

---

## 1. Philosophie : Du « Vaporware » des Réseaux aux Vrais Agents Exécutables

Les réseaux sociaux regorgent d'infographies théoriques promettant des dizaines d'agents IA autonomes sans aucune assise technique.  
**PyCRMKit prend le contre-pied absolu de cette approche :**
* Chaque agent défini dans ce répertoire repose sur un **moteur CRM transactionnel réel** (architecture hexagonale, transactions Unit of Work, validation d'invariants métier).
* Chaque skill fournit des **procédures déterministes et exécutables** via la CLI `pck` et le SDK Python `from pycrmkit.facade.crm import CRM`.
* Les agents n'hallucinent pas : ils manipulent des entités persistées (Organisations, Contacts, Opportunités, Pipelines, Tâches, Timeline, Custom Fields, Tags).

---

## 2. Cartographie des 5 Agents Métiers Spécialisés

| Agent | Rôle Stratégique | Cas d'Usage Couvert | Skills Associés |
|---|---|---|---|
| **`agency-copilot`** | Copilote Studio Web & MCO | Pilotage de studio web solo : avant-vente, devis, delivery logiciel, contrats de MCO, et formalisation des flux WhatsApp. | `agency-client-lifecycle`, `whatsapp-dialog-processor` |
| **`freelance-hunter`** | Chasseur de Missions & ATS | Recherche de missions en inter-contrat : suivi de candidatures, relances automatiques à J+5, négociation TJM et KPIs d'entonnoir. | `freelance-mission-hunter` |
| **`tender-bid-manager`** | Spécialiste Commande Publique | Réponse aux marchés publics & appels d'offres : analyse Go/No-Go, verrouillage de la DLRO à J-1, cotraitance GME et capitalisation des débriefings. | `public-tender-qualifier` |
| **`student-career-coach`** | Coach Insertion Professionnelle | Accompagnement d'étudiants & juniors : stages, alternances, premier emploi CDD/CDI, préparation d'entretiens et rapport pédagogique. | `student-career-launch` |
| **`association-coordinator`** | Coordinateur Vie Associative | Onboarding bénévoles, adhésions multi-canal, provisioning Microsoft 365, groupes WhatsApp et réadhésions annuelles (Diversité Alternative). | `association-member-onboarding` |

---

## 3. Répertoire des Skills Opérationnels

Les compétences spécialisées sont localisées dans `.agents/skills/` :

```text
.agents/skills/
├── agency-client-lifecycle/          # Pilotage commercial, delivery et maintenance MCO d'agence
├── whatsapp-dialog-processor/        # Extraction et formalisation des messages & vocaux WhatsApp
├── freelance-mission-hunter/         # Suivi de candidatures freelance, TJM et KPIs d'entonnoir
├── public-tender-qualifier/          # Analyse Go/No-Go, calendrier DLRO J-1 et mémoires techniques
├── student-career-launch/            # Gestion de candidatures stages/alternances et mémo d'entretiens
└── association-member-onboarding/    # Onboarding associatif, cotisations multi-canal, M365 et N+1
```

---

## 4. Règles d'Exécution pour les LLMs et Assistants IA

Lorsqu'un agent IA (Antigravity, OpenCode, Claude Code, etc.) intervient dans le cadre de ce dépôt :

1. **Priorité à l'Action Déterministe** :  
   Toujours privilégier les commandes CLI `pck` documentées dans les skills (`pck orgs`, `pck contacts`, `pck sales`, `pck tasks`, `pck dashboard`) ou les appels SDK Python. Ne jamais inventer d'étapes hors contrat.
2. **La Règle de l'Horodatage et des Délais** :  
   Pour les marchés publics, la tâche de dépôt DLRO **doit impérativement être fixée à J-1 à 16h00** avec la priorité `URGENT`.  
   Pour les candidatures freelance et étudiantes, la tâche de relance **doit être fixée à J+5**.
3. **Respect de l'Isolation Hexagonale** :  
   Les scripts ou automatisations créés par les agents ne doivent jamais importer directement de drivers de stockage physiques (`sqlalchemy`, `psycopg`) ; ils doivent passer exclusivement par la facade `CRM` ou la CLI `pck`.
4. **Conservation de la Mémoire Opposable** :  
   Chaque interaction client clé (décision orale, note vocale, retour de débriefing) doit être enregistrée dans la `crm.timeline` sous forme de note ou d'activité horodatée.
