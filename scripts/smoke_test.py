"""Installed-package smoke test for the current public CRM path."""

from __future__ import annotations

import pycrmkit


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.2.0a1":
        raise SystemExit(f"Expected PyCRMKit 0.2.0a1, got {version!r}")

    crm = pycrmkit.CRM.memory()
    contact = crm.contacts.create(first_name="Smoke", last_name="Test")
    loaded = crm.contacts.get(contact.id)
    if loaded.id != contact.id or loaded.display_name != "Smoke Test":
        raise SystemExit("CRM.memory() Contact smoke failed")

    activity = crm.activities.log(
        type="note",
        description="Installed package activity smoke",
    )
    loaded_activity = crm.activities.get(activity.id)
    if loaded_activity.id != activity.id or loaded_activity.type.value != "note":
        raise SystemExit("CRM.memory() Activity smoke failed")

    print(f"PyCRMKit {version}: CRM.memory() + Activities smoke OK")


if __name__ == "__main__":
    main()
