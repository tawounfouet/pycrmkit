"""Installed-package smoke test for the current public CRM path."""

from __future__ import annotations

import pycrmkit
from pycrmkit.activities import ActivityParticipant
from pycrmkit.core.references import EntityReference


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.2.0b1":
        raise SystemExit(f"Expected PyCRMKit 0.2.0b1, got {version!r}")

    crm = pycrmkit.CRM.memory()
    contact = crm.contacts.create(first_name="Smoke", last_name="Test")
    loaded = crm.contacts.get(contact.id)
    if loaded.id != contact.id or loaded.display_name != "Smoke Test":
        raise SystemExit("CRM.memory() Contact smoke failed")
    contact_ref = EntityReference("contact", contact.id)

    activity = crm.activities.log(
        type="note",
        description="Installed package activity smoke",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
    )
    loaded_activity = crm.activities.get(activity.id)
    if loaded_activity.id != activity.id or loaded_activity.type.value != "note":
        raise SystemExit("CRM.memory() Activity smoke failed")

    task = crm.tasks.create(
        title="Installed package task smoke",
        priority="high",
        references=(contact_ref,),
    )
    loaded_task = crm.tasks.get(task.id)
    if loaded_task.id != task.id or loaded_task.priority.name != "HIGH":
        raise SystemExit("CRM.memory() Task smoke failed")
    crm.tasks.complete(task.id)

    timeline = crm.timeline.for_contact(contact.id)
    if timeline.total != 3:
        raise SystemExit(f"CRM.memory() Timeline smoke failed: {timeline.total=}")

    print(
        f"PyCRMKit {version}: CRM.memory() + Activities + Tasks + Timeline smoke OK"
    )


if __name__ == "__main__":
    main()
