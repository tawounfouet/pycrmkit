# Alumni Directory Activation — Practical Examples & Recipes

> **Exemples Concrets, Commandes CLI & Recettes SDK**  
> **Skill Associé** : [`alumni-directory-activation`](SKILL.md)  
> **Workflow Détaillé** : [`workflow.md`](workflow.md)  
> **Cadre d'Application** : Réseaux d'Anciens Élèves & Écoles d'Ingénieurs

---

## Exemple 1 : Ingestion Sécurisée d'un CSV Google Forms

### Script d'import Django / CLI :
```python
import csv
from pycrmkit import CRM

crm = CRM.memory()

def sanitize_csv_cell(value: str) -> str:
    """Neutralise toute tentative d'injection de formule tableur."""
    cleaned = value.strip()
    if cleaned and cleaned[0] in ("=", "+", "-", "@"):
        return f"'{cleaned}"
    return cleaned

def import_alumni_responses(csv_filepath: str):
    with open(csv_filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            first_name = sanitize_csv_cell(row["Prénom"])
            last_name = sanitize_csv_cell(row["Nom"])
            email = sanitize_csv_cell(row["Adresse e-mail"]).lower()
            promo = int(row["Année de Promotion"])
            company = sanitize_csv_cell(row.get("Entreprise actuelle", ""))
            position = sanitize_csv_cell(row.get("Poste actuel", ""))
            
            # 1. Création ou déduplication du contact
            contact = crm.contacts.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                tags={f"promo-{promo}", "alumni-forms"},
                custom_fields={
                    "promo_year": promo,
                    "current_company": company,
                    "current_position": position,
                    "activation_status": "pending_invite",
                },
            )
            
            # 2. Rattachement de l'opportunité d'activation
            opp = crm.pipelines.create_opportunity(
                title=f"Activation {promo} - {first_name} {last_name}",
                contact_id=contact.id,
                pipeline_id="alumni-directory-activation",
                stage_id="formulaire_ingere",
                expected_value=0.0,
            )
            
            print(f"✅ Importé : {first_name} {last_name} ({promo}) - Contact: {contact.id}")

# Exemple d'appel :
# import_alumni_responses("reponses_annuaire_alumni_2026.csv")
```

---

## Exemple 2 : Génération des Jetons et Envoi de l'Email d'Invitation

### Envoi par lot avec mise à jour de la Timeline :
```python
import secrets
from datetime import datetime, timedelta

def dispatch_activation_invitations(promo_year: int):
    # Récupérer les contacts de la promo en attente d'invitation
    contacts = crm.contacts.filter(
        lambda c: f"promo-{promo_year}" in c.tags and c.custom_fields.get("activation_status") == "pending_invite"
    )
    
    for contact in contacts:
        # A. Création du token sécurisé (14 jours de validité)
        token = secrets.token_urlsafe(32)
        contact.custom_fields["activation_token"] = token
        contact.custom_fields["activation_token_expires_at"] = (datetime.now() + timedelta(days=14)).isoformat()
        contact.custom_fields["activation_status"] = "invite_sent"
        crm.contacts.save(contact)
        
        # B. Enregistrement dans la Timeline
        crm.timeline.record_activity(
            contact_id=contact.id,
            type="email_sent",
            title=f"Invitation Annuaire envoyée à {contact.first_name}",
            description=f"Lien : https://alumni.association.org/activate?token={token}",
        )
        
        # C. Avancement de l'opportunité au stage invitation_envoyee
        opps = crm.pipelines.list_opportunities_for_contact(contact.id)
        if opps:
            crm.pipelines.transition(
                opportunity_id=opps[0].id,
                to_stage="invitation_envoyee",
                metadata={"sent_at": datetime.now().isoformat()},
            )
            
    print(f"📨 {len(contacts)} invitations envoyées pour la promo {promo_year}.")
```

---

## Exemple 3 : Suivi J+7 & Génération du Message WhatsApp pour le Référent

### Extraction de la liste de relance ciblée :
```python
def generate_ambassador_reminder_pack(promo_year: int, ambassador_name: str) -> str:
    # Trouver les contacts non activés de cette promo ayant reçu l'invitation
    pending = crm.contacts.filter(
        lambda c: f"promo-{promo_year}" in c.tags and c.custom_fields.get("activation_status") == "invite_sent"
    )
    
    message = (
        f"Salut {ambassador_name} ! 🙌\n\n"
        f"Voici le point sur l'activation de l'annuaire pour la **Promo {promo_year}** :\n"
        f"Il reste **{len(pending)} camarades** qui n'ont pas encore cliqué sur leur lien d'activation :\n\n"
    )
    
    for c in pending:
        message += f"• {c.first_name} {c.last_name} ({c.custom_fields.get('current_company', 'N/C')})\n"
        
    message += (
        "\nPeux-tu glisser un mot amical sur le groupe WhatsApp de la promo pour leur rappeler "
        "qu'ils ont reçu un mail avec leur lien personnel d'activation ? Merci pour ton aide ! 🚀"
    )
    return message
```

---

## Exemple 4 : Vue Django d'Activation de Compte (`views.py`)

### Validation finale et passage au stage 100% Won :
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from pycrmkit import CRM

crm = CRM.memory()

def activate_alumni_account(request):
    token = request.GET.get("token") or request.POST.get("token")
    if not token:
        return render(request, "alumni/invalid_token.html", {"error": "Jeton manquant."})
    
    # 1. Rechercher le contact PyCRMKit possédant ce token
    matching_contacts = crm.contacts.filter(
        lambda c: c.custom_fields.get("activation_token") == token
    )
    if not matching_contacts:
        return render(request, "alumni/invalid_token.html", {"error": "Jeton invalide ou déjà utilisé."})
    
    contact = matching_contacts[0]
    
    if request.method == "POST":
        password = request.POST.get("password")
        
        # A. Créer ou activer le User Django
        user, created = User.objects.get_or_create(username=contact.email, defaults={"email": contact.email})
        user.first_name = contact.first_name
        user.last_name = contact.last_name
        user.set_password(password)
        user.is_active = True
        user.save()
        
        # B. Invalider le token et marquer le profil activé
        contact.custom_fields["activation_status"] = "activated"
        contact.custom_fields["activation_token"] = None
        contact.custom_fields["directory_visibility"] = "public_verified"
        crm.contacts.save(contact)
        
        # C. Valider l'opportunité PyCRMKit au stage compte_active (100% Won)
        opps = crm.pipelines.list_opportunities_for_contact(contact.id)
        if opps:
            crm.pipelines.transition(
                opportunity_id=opps[0].id,
                to_stage="compte_active",
                metadata={"activated_at": "now", "user_id": user.id},
            )
            
        # D. Consigner l'événement dans la Timeline
        crm.timeline.record_activity(
            contact_id=contact.id,
            type="account_activated",
            title="Compte Alumni Django Activé",
            description="Le membre s'est connecté et a validé son mot de passe.",
        )
        
        messages.success(request, "Votre compte est activé ! Bienvenue sur l'annuaire des anciens.")
        return redirect("alumni:directory")
        
    return render(request, "alumni/activate_form.html", {"contact": contact, "token": token})
```
