---
name: whatsapp-dialog-processor
description: >
  Parse unstructured WhatsApp messages, voice note transcripts, and phone calls
  into structured PyCRMKit CRM entities: convert inbound messages to Leads, log
  notes to Contact/Org timelines, create high-priority MCO tasks, and attach
  external WhatsApp identities (+336...).
user-invocable: true
---

# WhatsApp Dialog Processor

Use this skill whenever processing informal WhatsApp exchanges, voice note transcripts, or audio call summaries with clients, non-profit contacts, or network referrals.

## Core Rules

1. **La Règle des 30 Secondes** : Ne jamais laisser un accord oral, un budget ou une demande d'intervention se perdre dans un fil de discussion WhatsApp.
2. **Attachement d'Identité Externe** : Chaque contact WhatsApp doit posséder une `ExternalIdentity` avec `system="whatsapp"` et son numéro E.164.
3. **Formalisation Sans Chatbot** : Le CRM structure l'information en coulisse ; il ne répond pas à votre place pour préserver le lien humain direct.

---

## Processing Workflows

### 1. Inbound WhatsApp Referral / Lead
Quand un contact personnel ou associatif vous écrit sur WhatsApp pour un nouveau projet :

```bash
# 1. Enregistrement instantané du Lead avec source
pck leads create \
    --name "<Prénom Nom>" \
    --org "<Entreprise / Asso>" \
    --phone "<+336XXXXXXXX>" \
    --source "whatsapp_reseau"
```

En Python (avec attachement de l'identité WhatsApp) :
```python
from pycrmkit.core.references import EntityReference
from pycrmkit.facade.crm import CRM

crm = CRM()
contact = crm.contacts.create(first_name="Julien", last_name="Barret", email="julien@asso.fr", phone="+33612345678")

# Lier l'identité WhatsApp
crm.external_identities.attach(
    contact,
    system="whatsapp",
    external_id="+33612345678",
    metadata={"display_name": "Julien Asso Solidarité", "preferred_channel": True}
)
```

### 2. Synthèse de Note Vocale ou Accord Verbal
Quand le client valide un devis ou donne des directives dans un message vocal :

```bash
# 1. Déplacement du deal après accord vocal
pck sales move <deal-id> won

# 2. Consigner le compte-rendu dans la timeline
# Note : Enregistrement d'une note ou d'une activité horodatée
```

En Python SDK :
```python
crm.timeline.record_note(
    entity=EntityReference("organization", org.id),
    title="Accord Devis v1 via Note Vocale WhatsApp",
    content="Julien a confirmé son accord pour le forfait de 4 500 € HT. Début des dev fixé au 15/11. Acompte de 30% en cours de virement."
)
```

### 3. Signalement d'un Incident / Bug MCO sur WhatsApp
Quand un client en maintenance signale un dysfonctionnement (ex: le week-end ou en soirée) :

```bash
# Création immédiate d'une tâche prioritaire pour le prochain jour ouvré
pck tasks create \
    --title "[MCO WhatsApp] Erreur 500 signalée sur formulaire de paiement" \
    --entity-id <org-id> \
    --priority URGENT \
    --due "<YYYY-MM-DD>"
```

---

## Verification

Vérifier la bonne traçabilité sur la fiche client :
```bash
pck contacts show <contact-id>
pck orgs show <org-id>
```
La timeline affiche clairement l'historique des notes et la tâche urgente est visible dans `pck dashboard`.
