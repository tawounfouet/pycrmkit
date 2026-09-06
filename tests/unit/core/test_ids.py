from uuid import UUID

from pycrmkit.core import EntityId, IDFactory, UUID4Factory, UUIDId


class ContactId(UUIDId):
    pass


def test_uuid_id_parses_string_and_round_trips() -> None:
    raw = "12345678-1234-5678-1234-567812345678"

    entity_id = EntityId.parse(raw)

    assert entity_id.value == UUID(raw)
    assert str(entity_id) == raw
    assert EntityId.parse(entity_id) is entity_id


def test_uuid_factory_preserves_requested_identifier_type() -> None:
    factory = UUID4Factory()

    contact_id = factory.new(ContactId)

    assert isinstance(factory, IDFactory)
    assert isinstance(contact_id, ContactId)
    assert contact_id.value.version == 4


def test_typed_ids_with_same_uuid_are_not_equal_across_types() -> None:
    raw = UUID("12345678-1234-5678-1234-567812345678")

    assert EntityId(raw) != ContactId(raw)
