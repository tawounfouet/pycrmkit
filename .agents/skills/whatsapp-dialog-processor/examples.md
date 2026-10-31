# WhatsApp Dialog Processor — Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Scripts SDK**  
> **Skill Associé** : [`whatsapp-dialog-processor`](SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](workflow.md)

---

## Exemple 1 : Traitement d'un Message de Recommandation Réseau

### Message WhatsApp Reçu :
> *« Bonjour Thomas ! Je t'écris de la part d'Aminata de l'association Diversité Alternative. On cherche un dev pour développer notre plateforme de mentorat pour le premier trimestre 2027. On a un budget d'environ 15 000 €. Dis-moi si tu as 15 min cette semaine pour en discuter ! David (+33 6 88 77 66 55) »*

### Script d'Ingestion & Traçabilité :
```python
from pycrmkit import CRM
from pycrmkit.contacts import ContactPhone
from pycrmkit.core.references import EntityReference
from pycrmkit.external_identities import ExternalIdentity

crm = CRM.memory()

# 1. Création du contact David
david = crm.contacts.create(
    first_name="David",
    last_name="Mentorat",
    phones=(ContactPhone("+33688776655", is_primary=True),),
    source="whatsapp_referral",
)

# 2. Liaison de son identité WhatsApp
crm.external_identities.link(
    entity_kind="contact",
    entity_id=david.id,
    identity=ExternalIdentity(
        provider="whatsapp",
        external_id="+33688776655",
    ),
)

# 3. Création de l'opportunité avec le budget estimé
crm.opportunities.create(
    contact_id=david.id,
    title="Plateforme Mentorat Associatif",
    estimated_value=15000,
    currency="EUR",
    pipeline="agency-commercial",
    stage="decouverte",
)

# 4. Tâche de rappel immédiat
ref = EntityReference("contact", david.id)
crm.tasks.create(
    title="Proposer 2 créneaux d'appel à David (+33688776655)",
    references=(ref,),
    priority="HIGH",
    due_date="2026-11-02",
)
```

---

## Exemple 2 : Note Vocale Client Validant un Scope Supplémentaire

### Transcription de la Note Vocale (Client TotalEnergies Renewables) :
> *« Allô Thomas, j'ai vu ta proposition pour le module de monitoring météo en temps réel à 8 500 €. C'est parfait, on valide l'avenant. Fais partir la facture d'acompte directement à la compta. Merci ! »*

### Consignation Opposable & Déplacement Commercial en CLI :
```bash
# 1. Enregistrement de la validation orale dans la timeline du contact
pck contacts show contact_totalenergies

# 2. Avancement de l'avenant commercial vers le statut Gagné
pck sales move deal_module_meteo won --pipeline agency-commercial

# 3. Création de la tâche administrative
pck tasks create \
    --title "Émettre facture acompte 30% module météo (TotalEnergies)" \
    --priority HIGH \
    --due "2026-11-03"
```
