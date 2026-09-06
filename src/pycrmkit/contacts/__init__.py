"""Contacts domain module."""

from pycrmkit.contacts.dto import UNSET, ContactUpdate
from pycrmkit.contacts.entities import Contact, ContactId, ContactStatus
from pycrmkit.contacts.queries import ContactQuery
from pycrmkit.contacts.repository import ContactRepository
from pycrmkit.contacts.services import ContactService
from pycrmkit.contacts.value_objects import (
    Address,
    ContactEmail,
    ContactPhone,
    VerificationState,
    normalize_email,
    normalize_phone,
)

__all__ = [
    "UNSET",
    "Address",
    "Contact",
    "ContactEmail",
    "ContactId",
    "ContactPhone",
    "ContactQuery",
    "ContactRepository",
    "ContactService",
    "ContactStatus",
    "ContactUpdate",
    "VerificationState",
    "normalize_email",
    "normalize_phone",
]
