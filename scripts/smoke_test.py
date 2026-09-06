"""Installed-package smoke test for the stable CRM Core path."""

from __future__ import annotations

import pycrmkit


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.1.0":
        raise SystemExit(f"Expected PyCRMKit 0.1.0, got {version!r}")

    crm = pycrmkit.CRM.memory()
    contact = crm.contacts.create(first_name="Smoke", last_name="Test")
    loaded = crm.contacts.get(contact.id)
    if loaded.id != contact.id or loaded.display_name != "Smoke Test":
        raise SystemExit("CRM.memory() installed-package smoke failed")

    print(f"PyCRMKit {version}: CRM.memory() smoke OK")


if __name__ == "__main__":
    main()
