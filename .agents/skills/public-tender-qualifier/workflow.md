# Public Tender Qualifier — Detailed Workflow & Architecture

> **Guide Opérationnel Détaillé & Commande Publique**  
> **Skill Associé** : [`public-tender-qualifier`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/public-tender-qualifier/SKILL.md)  
> **Exemples Concrets** : [`examples.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/public-tender-qualifier/examples.md)

---

## 1. Cycle de Vie d'une Réponse à Marché Public

La commande publique impose un formalisme strict régi par le Code de la Commande Publique :

```mermaid
flowchart TD
    subgraph Veille ["1. Veille & Ingestion"]
        BOAMP[BOAMP / PLACE / JOUE] --> Avis[Avis d'Appel Public à Concurrence]
        Avis --> Dossier[Téléchargement DCE : RC + CCTP + CCAP + BPU]
    end

    subgraph GoNoGo ["2. Décision Go / No-Go (Scorecard)"]
        Dossier --> Matrix{Matrice d'Éligibilité}
        Matrix -->|Score >= 75/100| Go[GO : Passage en Rédaction]
        Matrix -->|Score < 75/100| NoGo[NO-GO : Archivage Motivé]
    end

    subgraph Redaction ["3. Préparation de l'Offre & Verrou J-1"]
        Go --> Admin[Candidature Administrative : DC1, DC2, DUME, NOTI2]
        Go --> Tech[Offre Technique : Mémoire Justificatif Structuré]
        Go --> Price[Offre Financière : BPU / DPGF / DQE]
        Admin & Tech & Price --> Review[Revue Croisée Qualité & Signature Électronique]
        Review --> Lock[Verrouillage DLRO : Dépôt Ferme à J-1 16h00]
    end

    subgraph Attribution ["4. Jugement des Offres & Débriefing"]
        Lock --> Decision{Attribution par l'Acheteur}
        Decision -->|Attribué 🎉| Won[Notification Marché + Ordre de Service]
        Decision -->|Rejeté ❌| Debrief[Demande Grille de Notation & Bilan REX]
    end
```

---

## 2. Définition des Étapes du Pipeline `public-tenders-bid-management`

| Stage ID | Nom de l'Étape | Probabilité | Exigence Métier |
|---|---|---|---|
| `veille_dce` | DCE Téléchargé & Veille | 10 % | Analyse du Règlement de Consultation (RC) et du CCTP. |
| `go_decision` | Qualification Go / No-Go | 30 % | Validation formelle par le chef d'entreprise / directeur de pôle. |
| `redaction_reponse` | Rédaction Mémoire & Prix | 60 % | Rédaction du mémoire technique, constitution du GME si cotraitance. |
| `depot_effectue` | Pli Déposé sur Plateforme | 85 % | Récépissé horodaté téléchargé depuis PLACE/AWS/Maximilien. |
| `audition_orale` | Soutenance / Négociation | 90 % | Présentation devant la commission d'appel d'offres (si prévue au RC). |
| `marche_attribue` | Marché Notifié (*Won*) | 100 % | Réception de la lettre d'attribution et de l'acte d'engagement signé. |
| `offre_rejetee` | Rejet & Débriefing (*Lost*) | 0 % | Capitalisation des notes techniques/prix pour les futurs dossiers. |

---

## 3. Matrice de Décision Go / No-Go (Scorecard /100)

| Critère d'Évaluation | Poids | Condition d'Élimination Directe (*Red Flag*) |
|---|---|---|
| **Adéquation Technique (CCTP)** | 35 pts | Si moins de 85% des livrables maîtrisés sans sous-traitance $\rightarrow$ **NO-GO**. |
| **Pondération des Critères** | 25 pts | Si le Prix représente plus de 70% de la note finale $\rightarrow$ **NO-GO** (guerre des prix). |
| **Calendrier & Disponibilité** | 20 pts | Si la DLRO est inférieure à 10 jours ouvrés sans équipe mobilisée $\rightarrow$ **NO-GO**. |
| **Rentabilité & Marge Cible** | 20 pts | Si la marge brute estimée est inférieure à 25 % $\rightarrow$ **NO-GO**. |

> **Règle absolue** : Seul un score $\ge 75/100$ sans aucun *Red Flag* permet de passer au stage `redaction_reponse`.
