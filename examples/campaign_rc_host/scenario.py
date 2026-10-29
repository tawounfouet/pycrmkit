"""End-to-end signed-host Campaign qualification against migrated PostgreSQL.

Run from an external directory using the installed PyCRMKit wheel, never the
editable checkout. All data is synthetic and this DB MUST be disposable.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.metadata
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from host_app import _owner, create_app

import pycrmkit
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationDirection,
    CommunicationRecord,
    CommunicationRecordId,
)
from pycrmkit.core.references import EntityReference

ISSUER = "pycrmkit-rc1-host-fixture"
AUDIENCE = "pycrmkit-campaign-host"


def signed_token(
    tenant: str, *,
    expires_offset: int = 600,
    secret: str,
    audience: str = AUDIENCE,
) -> str:
    """Token issuer lives ONLY in this disposable test script, never the host."""
    now = int(time.time())
    data = json.dumps({
        "iss": ISSUER, "aud": audience,
        "tenant": tenant, "sub": "integration-test-actor",
        "role": "campaign_admin", "iat": now, "exp": now + expires_offset,
    }, sort_keys=True, separators=(",", ":")).encode()
    mac = hmac.digest(secret.encode(), data, hashlib.sha256)
    def encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return encode(data) + "." + encode(mac)


def record(host: object, *, tenant: str) -> CommunicationRecordId:
    resources = host.state.pycrmkit_host
    now = datetime.now(UTC)
    identifier = CommunicationRecordId(uuid4())
    communication = CommunicationRecord(
        id=identifier, created_at=now, updated_at=now, occurred_at=now,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        counterparties=(CommunicationAddress(
            CommunicationChannel.EMAIL, f"private-{tenant}@example.test",
        ),),
        subject=f"PRIVATE {tenant} synthetic communication",
        metadata={"tenant": tenant},
    )
    with resources.uow() as uow:
        uow.communications.save_record(communication)
        uow.commit()
    return identifier


def main() -> None:
    repo = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    assert not Path(pycrmkit.__file__).resolve().is_relative_to(repo), (
        "Test imported PyCRMKit from checkout instead of installed wheel"
    )
    assert importlib.metadata.version("pycrmkit") == os.environ["PYCRMKIT_EXPECTED_VERSION"]
    database_url = os.environ["PYCRMKIT_DATABASE_URL"]
    secret = os.environ["PYCRMKIT_RC_HOST_SIGNING_KEY"]

    app = create_app(database_url)
    resources = app.state.pycrmkit_host
    crm = resources.crm
    alice_owner, bob_owner = _owner("alice"), _owner("bob")
    alice_a = crm.contacts.create(display_name="Synthetic Alice A", owner_id=alice_owner)
    alice_b = crm.contacts.create(display_name="Synthetic Alice B", owner_id=alice_owner)
    bob_contact = crm.contacts.create(display_name="Synthetic Bob", owner_id=bob_owner)
    segment = crm.segments.create_static(
        key="rc14-alice-segment", name="Synthetic Alice Segment",
        entity_kind="contact", owner_id=alice_owner,
    )
    other_segment = crm.segments.create_static(
        key="rc14-bob-segment", name="Synthetic Bob Segment",
        entity_kind="contact", owner_id=bob_owner,
    )
    crm.segments.add_member(
        segment.id, EntityReference("contact", alice_a.id),
    )
    crm.segments.add_member(
        other_segment.id, EntityReference("contact", bob_contact.id),
    )
    own_record, foreign_record = record(app, tenant="alice"), record(app, tenant="bob")

    auth_alice = {"Authorization": "Bearer " + signed_token("alice", secret=secret)}
    auth_bob = {"Authorization": "Bearer " + signed_token("bob", secret=secret)}
    unauthorized = {"X-Actor-ID": "admin", "X-Correlation-ID": "forged"}
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert "/crm/contacts" not in app.openapi()["paths"]
        assert "/crm/segments" not in app.openapi()["paths"]
        assert client.post("/crm/campaigns", headers=auth_alice, json={
            "key": "unsafe-generic-create", "name": "Unsafe",
            "owner_id": str(bob_owner),
        }).status_code == 403
        assert client.post("/host/campaigns", json={
            "key": "no-credentials", "name": "No credentials",
        }).status_code == 401
        assert client.post("/host/campaigns", headers=unauthorized, json={
            "key": "forged", "name": "Forged",
        }).status_code == 401

        invalid_token = signed_token("alice", secret=secret) + "X"
        assert client.get("/crm/campaigns", headers={
            "Authorization": "Bearer " + invalid_token,
        }).status_code == 401
        assert client.get("/crm/campaigns", headers={
            "Authorization": "Bearer " + signed_token(
                "alice", secret=secret, expires_offset=-1,
            ),
        }).status_code == 401
        assert client.get("/crm/campaigns", headers={
            "Authorization": "Bearer " + signed_token(
                "alice", secret=secret, audience="wrong-service",
            ),
        }).status_code == 401

        created = client.post("/host/campaigns", headers=auth_alice, json={
            "key": "rc14-alice", "name": "Alice Campaign",
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["id"]
        assert created.json()["owner_id"] == str(alice_owner)
        bob = client.post("/host/campaigns", headers=auth_bob, json={
            "key": "rc14-bob", "name": "Bob Campaign",
        })
        assert bob.status_code == 201, bob.text
        bob_id = bob.json()["id"]
        base = f"/crm/campaigns/{campaign_id}"
        host_base = f"/host/campaigns/{campaign_id}"

        before = resources.factory_calls
        for path, headers in (
            (base, unauthorized),
            (base, auth_bob),
            (f"{base}/audience/count", auth_bob),
            (f"{base}/attributions", auth_bob),
            (f"/crm/campaigns/{bob_id}", auth_alice),
        ):
            response = client.get(path, headers=headers)
            assert response.status_code in {401, 403}, response.text
            assert "total" not in response.json()
            assert "count" not in response.json()
            assert "private" not in response.text.lower()
        assert resources.factory_calls == before, "host denial invoked CRM factory"

        invalid_list = client.get(
            "/crm/campaigns", headers=auth_alice,
            params={"owner_id": str(bob_owner)},
        )
        assert invalid_list.status_code == 403
        owned_list = client.get(
            "/crm/campaigns", headers=auth_alice,
            params={"owner_id": str(alice_owner), "limit": 1},
        )
        assert owned_list.status_code == 200
        assert owned_list.json()["total"] == 1
        assert owned_list.json()["items"][0]["id"] == campaign_id

        assert client.patch(base, headers=auth_alice, json={
            "expected_revision": 1, "owner_id": str(bob_owner),
        }).status_code == 403
        assert client.post(base + "/segment-sources", headers=auth_alice, json={
            "segment_id": str(other_segment.id),
        }).status_code == 403
        wrong_segment = client.post(
            host_base + f"/capture/{other_segment.id}", headers=auth_alice,
        )
        assert wrong_segment.status_code == 403
        captured = client.post(
            host_base + f"/capture/{segment.id}", headers=auth_alice,
        )
        assert captured.status_code == 201, captured.text
        assert captured.json() == {"member_count": 1}
        assert client.get(base + "/audience/count", headers=auth_alice).json() == {
            "count": 1
        }

        injected = client.post(
            host_base + "/import", headers=auth_alice,
            json={"rows": [
                {"entity_kind": "contact", "entity_id": str(alice_b.id)},
                {"entity_kind": "contact", "entity_id": str(bob_contact.id)},
            ]},
        )
        assert injected.status_code == 403, injected.text
        assert client.get(base + "/members", headers=auth_alice).json()["total"] == 0
        assert client.post(base + "/members", headers=auth_alice, json={
            "members": [{"kind": "contact", "id": str(bob_contact.id)}],
        }).status_code == 403

        rows = {"rows": [
            {"entity_kind": "contact", "entity_id": str(alice_a.id)},
            {"entity_kind": "contact", "entity_id": str(alice_b.id)},
        ]}
        first = client.post(host_base + "/import", headers=auth_alice, json=rows)
        assert first.status_code == 200, first.text
        assert first.json()["rows_created"] == 2
        replay = client.post(host_base + "/import", headers=auth_alice, json=rows)
        assert replay.status_code == 200, replay.text
        assert replay.json()["rows_created"] == 0
        assert replay.json()["duplicates"] == 2
        assert client.get(base + "/audience/count", headers=auth_alice).json() == {
            "count": 2
        }
        exported = client.get(host_base + "/export", headers=auth_alice)
        assert exported.status_code == 200
        data = [json.loads(line) for line in exported.text.splitlines()]
        assert {x["entity_id"] for x in data} == {str(alice_a.id), str(alice_b.id)}
        assert "PRIVATE" not in exported.text
        assert "bob" not in exported.text.lower()
        assert client.get(host_base + "/export", headers=auth_bob).status_code == 403

        assert client.post(base + "/attributions", headers=auth_alice, json={
            "target": {"kind": "contact", "id": str(bob_contact.id)},
            "source": "forbidden",
        }).status_code == 403
        assert client.post(host_base + "/attribution", headers=auth_alice, json={
            "contact_id": str(bob_contact.id), "source": "linkedIn",
        }).status_code == 403
        attributed = client.post(host_base + "/attribution", headers=auth_alice, json={
            "contact_id": str(alice_a.id), "source": " LinkedIn ",
        })
        assert attributed.status_code == 201, attributed.text
        assert attributed.json()["source"] == "linkedin"

        wrong_link = client.post(
            host_base + f"/communication/{foreign_record}", headers=auth_alice,
        )
        assert wrong_link.status_code == 403
        assert client.post(base + "/communication-links", headers=auth_alice, json={
            "communication_id": str(foreign_record),
        }).status_code == 403
        linked = client.post(
            host_base + f"/communication/{own_record}", headers=auth_alice,
        )
        assert linked.status_code == 201, linked.text
        assert linked.json()["communication_id"] == str(own_record)
        assert "subject" not in linked.text
        assert "counterparties" not in linked.text
        assert crm.campaigns.communication_links(
            pycrmkit.campaigns.CampaignId.parse(campaign_id),
        ).total == 1
        assert crm.campaigns.attributions(
            pycrmkit.campaigns.CampaignId.parse(campaign_id),
        ).total == 1

    resources.engine.dispose()

    # Real new Engine/CRM instance: state must be persisted in PostgreSQL.
    restarted = create_app(database_url)
    with TestClient(restarted) as client:
        own = client.get(f"/crm/campaigns/{campaign_id}", headers=auth_alice)
        assert own.status_code == 200 and own.json()["owner_id"] == str(alice_owner)
        assert client.get(
            f"/crm/campaigns/{campaign_id}/audience/count",
            headers=auth_alice,
        ).json() == {"count": 2}
        assert client.get(
            f"/crm/campaigns/{campaign_id}/attributions",
            headers=auth_alice,
        ).json()["total"] == 1
        assert client.get(
            f"/crm/campaigns/{campaign_id}",
            headers=auth_bob,
        ).status_code == 403
        assert restarted.state.pycrmkit_host.crm.campaigns.communication_links(
            pycrmkit.campaigns.CampaignId.parse(campaign_id),
        ).total == 1
    restarted.state.pycrmkit_host.engine.dispose()

    print(
        "LOT-31-014 installed-wheel FastAPI host + PostgreSQL 17: "
        "PASS (signed principal, tenant checks, full Campaign journey, restart)"
    )


if __name__ == "__main__":
    main()
