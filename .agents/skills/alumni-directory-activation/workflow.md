# Alumni Directory Activation — Detailed Workflow & Architecture

> **Guide Opérationnel Détaillé & Cycle de Vie de l'Annuaire Alumni**  
> **Skill Associé** : [`alumni-directory-activation`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/alumni-directory-activation/SKILL.md)  
> **Exemples Concrets** : [`examples.md`](file:///Users/awf/workspace/professionnal/webtech/packages/pycrmkit/.agents/skills/alumni-directory-activation/examples.md)  
> **Cadre d'Application** : Réseaux d'Anciens Élèves, Écoles & Universités intégrant avec Django

---

## 1. Vue d'Ensemble de l'Architecture Multi-Rôles

Le déploiement d'un annuaire d'anciens mobilise 4 piliers coordonnés :

```mermaid
flowchart TD
    subgraph Sourcing ["1. Mobilisation Décentralisée"]
        Ambassador[Référents de Promotion Nommés] -->|Diffusion Liens WhatsApp| PromoGroup[Groupes WhatsApp Promo]
        PromoGroup --> GForms[Google Forms Annuaire Rempli]
        GForms --> Export[Export CSV / Excel du Bureau]
    end

    subgraph DataOps ["2. Ingestion Sécurisée & Déduplication"]
        Export --> CSVGuard[Filtre Anti-Injection Tableur (=, +, -, @)]
        CSVGuard --> DedupEngine[Moteur Dédup : Email & Nom + Prénom + Promo]
        DedupEngine -->|Nouveau| CreateContact[Création Fiche Contact & Tags Promo]
        DedupEngine -->|Existant| MergeContact[Fusion Enrich_Missing]
        CreateContact & MergeContact --> OppCreate[Opportunité créée : formulaire_ingere]
    end

    subgraph Activation ["3. Invitation Tokenisée & Activation Django"]
        OppCreate --> TokenGen[Génération Jeton Unique /activate?token=...]
        TokenGen --> EmailDispatch[Envoi Email Invitation Personnalisé]
        EmailDispatch --> OppSent[Stage : invitation_envoyee]
        OppSent --> UserClick{L'alumni clique sous 7 jours ?}
        UserClick -->|Oui| PwdSetup[Formulaire Django /activate : Mot de Passe]
        PwdSetup --> UserActive[Django User.is_active = True]
        UserActive --> Won[Stage : compte_active 🎉 (100% Won)]
    end

    subgraph Relance ["4. Relance Ciblée par Référent de Promo"]
        UserClick -->|Non| Expired[Stage : relance_j7]
        Expired --> PromoReport[Rapport synthétique par promo]
        PromoReport --> WARelance[Relance amicale WhatsApp par le Référent]
        WARelance --> UserClick
    end
```

---

## 2. Définition des Étapes du Pipeline `alumni-directory-activation`

| Stage ID | Nom Affiché | Probabilité | SLA & Action Requise |
|---|---|---|---|
| `formulaire_ingere` | Formulaire Reçu & Dédupliqué | 20 % | Ingestion sous 24h, assainissement des chaînes et déduplication. |
| `fiche_qualifiee` | Fiche Qualifiée & Complète | 40 % | Validation des informations académiques (promo, filière, email pro/perso). |
| `invitation_envoyee` | Invitation Envoyée avec Token | 60 % | Génération du token (validité 14 jours), consignation timeline, envoi email. |
| `relance_j7` | Relance J+7 (Alerte Référent) | 50 % | Notification automatique au référent de promo si aucun clic après 7 jours. |
| `compte_active` | Compte Activé & Annuaire Opérationnel | 100 % (Won) | Compte Django actif (`is_active = True`), statut vérifié dans l'annuaire. |
| `desinscription` | Opt-out / Refus Annuaire | 0 % (Lost) | Volonté expresse de ne pas figurer dans l'annuaire public. |

---

## 3. Matrice de Déduplication & Règles DataOps

Pour garantir l'intégrité de l'annuaire sans bloquer la mise à jour des coordonnées par les alumnis :

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MATRICE DÉCISIONNELLE DE DÉDUPLICATION                          │
├──────────────────────┬────────────────────────────────────┬────────────────────────────┤
│ Condition de Match   │ Degré de Certitude                 │ Action PyCRMKit            │
├──────────────────────┼────────────────────────────────────┼────────────────────────────┤
│ Email exact          │ 100% Certain                       │ Fusionner (enrich_missing) │
│ (Nom, Prénom, Promo) │ 90% (Forte présomption d'homonyme) │ Rattacher comme alias/note │
│ Phone exact          │ 85%                                │ Alerter admin de doublon   │
│ Inconnu              │ 0% (Nouveau profil)                │ Création nouveau contact   │
└──────────────────────┴────────────────────────────────────┴────────────────────────────┘
```

### Protection Anti-Injection Tableur (CSV/Excel Formula Injection)

Les formulaires Google Forms ouverts permettent à n'importe quel répondant de saisir des chaînes piégées. PyCRMKit applique une neutralisation stricte :
* Toute cellule débutant par `=`, `+`, `-`, `@` est préfixée d'une apostrophe `'` lors de l'ingestion.
* Les retours chariot intempestifs et espaces insécables sont normalisés.

---

## 4. Modélisation de la Relation Référent de Promo

La relation entre un alumni et sa promotion s'appuie sur le graphe de relations PyCRMKit :

```python
# Modélisation d'un référent de promotion
crm.relationships.create(
    from_entity=EntityReference.for_contact(ambassador_contact_id),
    to_entity=EntityReference.for_custom("promotion", "promo-2018"),
    relation_type="ambassador_of",
    metadata={"assigned_at": "2026-09-01", "role": "Référent Promo 2018"},
)
```

Ce graphe permet d'extraire en une seule commande la cohorte d'anciens associée à un ambassadeur et d'alimenter son tableau de bord d'activation.

---

## 5. Intégration Native Django & Cycle de Vie du Compte

Dans l'application Django hôte, l'activation ne crée pas un silo isolé :
1. **L'écouteur de signal d'activation** met à jour le modèle `User` :
   ```python
   user.is_active = True
   user.set_password(new_password)
   user.save()
   ```
2. **Le Unit of Work PyCRMKit** valide la transition de l'opportunité :
   ```python
   crm.pipelines.transition(
       opportunity_id=opp_id,
       to_stage="compte_active",
       metadata={"activated_via": "web_token"},
   )
   ```
3. L'alumni est instantanément visible dans la vue publique `/annuaire/` de l'association.
