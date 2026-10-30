"""LOT-32-007: installed-wheel reference host stable acceptance.

Execute outside the repository checkout, against a migrated disposable
PostgreSQL database. The signer is test-only, not production IAM.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import pycrmkit
from host_app import _owner, create_app
from scenario import record, signed_token
from pycrmkit.campaigns import CampaignId
from pycrmkit.core.references import EntityReference


def main() -> None:
    checkout = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    imported = Path(pycrmkit.__file__).resolve()
    assert not imported.is_relative_to(checkout), "Source checkout masqueraded as wheel"
    assert importlib.metadata.version("pycrmkit") == "1.2.0rc1"
    assert pycrmkit.__version__ == "1.2.0rc1"

    url = os.environ["PYCRMKIT_DATABASE_URL"]
    assert url.startswith("postgresql+psycopg://")
    assert "pycrmkit_stable_" in url.split("/")[-1], "Disposable database required"
    secret = os.environ["PYCRMKIT_RC_HOST_SIGNING_KEY"]
    assert len(secret.encode("utf-8")) >= 32

    app = create_app(url)
    state = app.state.pycrmkit_host
    crm = state.crm
    alice = _owner("alice")
    bob = _owner("bob")

    own_a = crm.contacts.create(display_name="Private Alice First", owner_id=alice)
    own_b = crm.contacts.create(display_name="Private Alice Second", owner_id=alice)
    foreign = crm.contacts.create(display_name="Private Bob Only", owner_id=bob)
    contaminated = crm.segments.create_static(
        key="stable-host-contaminated", name="Foreign member fixture",
        entity_kind="contact", owner_id=alice,
    )
    crm.segments.add_member(
        contaminated.id, EntityReference("contact", foreign.id)
    )
    clean = crm.segments.create_static(
        key="stable-host-clean", name="Clean snapshot",
        entity_kind="contact", owner_id=alice,
    )
    crm.segments.add_member(clean.id, EntityReference("contact", own_a.id))
    own_communication = record(app, tenant="alice")
    foreign_communication = record(app, tenant="bob")

    alice_headers = {
        "Authorization": "Bearer " + signed_token("alice", secret=secret),
        "X-Actor-ID": "bob",
    }
    bob_headers = {
        "Authorization": "Bearer " + signed_token("bob", secret=secret),
        "X-Actor-ID": "alice",
    }
    with TestClient(app) as client:
        routes = app.openapi()["paths"]
        assert "/host/campaigns" in routes
        assert "/crm/campaigns" in routes
        assert "/crm/contacts" not in routes
        assert "/crm/segments" not in routes

        before = state.factory_calls
        for token_headers in (
            {},
            {"X-Actor-ID": "alice"},
            {"Authorization": "Bearer " + signed_token(
                "alice", secret=secret, expires_offset=-1
            )},
            {"Authorization": "Bearer " + signed_token(
                "alice", secret=secret, audience="other-service"
            )},
        ):
            response = client.post(
                "/host/campaigns",
                headers=token_headers,
                json={"key": "no-authority", "name": "Denied"},
            )
            assert response.status_code == 401, response.text
            assert "total" not in response.json()
        assert state.factory_calls == before, "Bad claims reached CRM factory"

        forged_owner = client.post(
            "/host/campaigns", headers=alice_headers,
            json={
                "key": "forged-owner", "name": "No",
                "owner_id": str(bob),
            },
        )
        assert forged_owner.status_code == 422, forged_owner.text
        assert state.factory_calls == before

        owned = client.post(
            "/host/campaigns", headers=alice_headers,
            json={"key": "stable-host-alice", "name": "Reference Tenant"},
        )
        assert owned.status_code == 201, owned.text
        cid = owned.json()["id"]
        assert owned.json()["owner_id"] == str(alice)

        other = client.post(
            "/host/campaigns", headers=bob_headers,
            json={"key": "stable-host-bob", "name": "Other Tenant"},
        )
        assert other.status_code == 201, other.text
        foreign_cid = other.json()["id"]
        host_url = f"/host/campaigns/{cid}"
        core_url = f"/crm/campaigns/{cid}"

        before = state.factory_calls
        for verb, path, headers in (
            ("get", host_url + "/export", bob_headers),
            ("post", host_url + "/import", bob_headers),
            ("post", host_url + "/capture/" + str(clean.id), bob_headers),
            ("post", host_url + "/attribution", bob_headers),
            ("post", host_url + "/communication/" + str(own_communication), bob_headers),
            ("get", f"/crm/campaigns/{foreign_cid}/audience/count", alice_headers),
            ("get", core_url + "/attributions", bob_headers),
            ("get", core_url + "/communication-links", bob_headers),
        ):
            payload = None
            if path.endswith("/import"):
                payload = {"rows": [
                    {"entity_kind": "contact", "entity_id": str(own_a.id)}
                ]}
            elif path.endswith("/attribution"):
                payload = {"contact_id": str(own_a.id), "source": "verified"}
            response = client.request(
                verb.upper(), path, headers=headers, json=payload,
            )
            assert response.status_code == 403, (path, response.text)
            assert "total" not in response.json()
            assert "count" not in response.json()
            assert "Private" not in response.text
        assert state.factory_calls == before, "Cross-tenant denial invoked CRM factory"

        assert client.post(
            core_url + "/members", headers=alice_headers,
            json={"members": [
                {"kind": "contact", "id": str(foreign.id)}
            ]},
        ).status_code == 403

        # A Segment with the CORRECT owner but a foreign member is unsafe.
        rejected_capture = client.post(
            host_url + "/capture/" + str(contaminated.id),
            headers=alice_headers,
        )
        assert rejected_capture.status_code == 403, rejected_capture.text
        assert crm.campaigns.segment_sources(CampaignId.parse(cid)).total == 0
        assert crm.campaigns.audience_count(CampaignId.parse(cid)) == 0

        accepted_capture = client.post(
            host_url + "/capture/" + str(clean.id), headers=alice_headers
        )
        assert accepted_capture.status_code == 201, accepted_capture.text
        assert accepted_capture.json() == {"member_count": 1}

        # Host input validation MUST reject oversized payloads without writes.
        oversized = client.post(
            host_url + "/import", headers=alice_headers,
            json={"rows": [
                {"entity_kind": "contact", "entity_id": str(own_a.id)}
                for _ in range(1001)
            ]},
        )
        assert oversized.status_code == 422, oversized.text
        assert crm.campaigns.members(CampaignId.parse(cid)).total == 0

        # All references are validated before the *first* write.
        mixed = client.post(
            host_url + "/import", headers=alice_headers,
            json={"rows": [
                {"entity_kind": "contact", "entity_id": str(own_b.id)},
                {"entity_kind": "contact", "entity_id": str(foreign.id)},
            ]},
        )
        assert mixed.status_code == 403, mixed.text
        assert crm.campaigns.members(CampaignId.parse(cid)).total == 0

        missing = client.post(
            host_url + "/import", headers=alice_headers,
            json={"rows": [
                {"entity_kind": "contact", "entity_id": str(own_b.id)},
                {"entity_kind": "contact", "entity_id": str(uuid4())},
            ]},
        )
        assert missing.status_code == 404, missing.text
        assert crm.campaigns.members(CampaignId.parse(cid)).total == 0

        events: list[object] = []
        state.event_bus.subscribe("campaign.member_added", events.append)
        valid_rows = {"rows": [
            {"entity_kind": "contact", "entity_id": str(own_a.id)},
            {"entity_kind": "contact", "entity_id": str(own_b.id)},
        ]}
        imported = client.post(
            host_url + "/import", headers=alice_headers, json=valid_rows
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["rows_created"] == 2
        assert imported.json()["validation_errors"] == 0
        assert len(events) == 2
        replay = client.post(
            host_url + "/import", headers=alice_headers, json=valid_rows
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["rows_created"] == 0
        assert replay.json()["duplicates"] == 2
        assert len(events) == 2

        total = client.get(
            core_url + "/audience/count", headers=alice_headers
        )
        assert total.status_code == 200
        assert total.json() == {"count": 2}

        exported = client.get(host_url + "/export", headers=alice_headers)
        assert exported.status_code == 200, exported.text
        assert "ndjson" in exported.headers["content-type"]
        values = [json.loads(line) for line in exported.text.splitlines()]
        assert {v["entity_id"] for v in values} == {
            str(own_a.id), str(own_b.id)
        }
        assert all(
            set(v) == {"campaign_id", "entity_kind", "entity_id"} for v in values
        )
        for confidential in ("Private Alice", "Private Bob", "subject", "counterparties"):
            assert confidential not in exported.text

        denied_attr = client.post(
            host_url + "/attribution", headers=alice_headers,
            json={"contact_id": str(foreign.id), "source": "referral"},
        )
        assert denied_attr.status_code == 403
        accepted_attr = client.post(
            host_url + "/attribution", headers=alice_headers,
            json={"contact_id": str(own_a.id), "source": " Conference  "},
        )
        assert accepted_attr.status_code == 201, accepted_attr.text
        assert accepted_attr.json() == {"source": "conference"}

        denied_link = client.post(
            host_url + "/communication/" + str(foreign_communication),
            headers=alice_headers,
        )
        assert denied_link.status_code == 403, denied_link.text
        accepted_link = client.post(
            host_url + "/communication/" + str(own_communication),
            headers=alice_headers,
        )
        assert accepted_link.status_code == 201, accepted_link.text
        assert accepted_link.json()["communication_id"] == str(own_communication)
        assert "PRIVATE" not in accepted_link.text
        assert "subject" not in accepted_link.text

    state.engine.dispose()

    restarted = create_app(url)
    with TestClient(restarted) as client:
        own = client.get(
            f"/crm/campaigns/{cid}", headers=alice_headers
        )
        assert own.status_code == 200, own.text
        assert own.json()["owner_id"] == str(alice)
        assert client.get(
            f"/crm/campaigns/{cid}/audience/count", headers=alice_headers
        ).json() == {"count": 2}
        assert client.get(
            f"/crm/campaigns/{cid}/attributions", headers=alice_headers
        ).json()["total"] == 1
        assert client.get(
            f"/crm/campaigns/{cid}/communication-links", headers=alice_headers
        ).json()["total"] == 1
        assert client.get(
            f"/crm/campaigns/{cid}", headers=bob_headers
        ).status_code == 403
        assert client.get(
            f"/host/campaigns/{cid}/export", headers=bob_headers
        ).status_code == 403
    restarted.state.pycrmkit_host.engine.dispose()

    print(
        "LOT-32-007 installed wheel + migrated PostgreSQL reference host: "
        "PASS (signed/tenant denial, contaminated Segment, preflight, "
        "replay, privacy, linkage and restart)"
    )


if __name__ == "__main__":
    main()
