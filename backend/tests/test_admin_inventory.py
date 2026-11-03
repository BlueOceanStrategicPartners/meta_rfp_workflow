import pytest

from apps.admin_command_center.models import AdminAuditEvent
from apps.inventory.models import SpaceInventory, VenueProperty


@pytest.mark.django_db
def test_property_crud(admin_client):
    res = admin_client.post("/api/admin-center/inventory/properties/", {"name": "Harbour Hotel"}, format="json")
    assert res.status_code == 201
    pid = res.json()["id"]
    assert res.json()["space_count"] == 0
    assert admin_client.patch(
        f"/api/admin-center/inventory/properties/{pid}/", {"name": "Harbour Grand"}, format="json"
    ).json()["name"] == "Harbour Grand"
    assert admin_client.delete(f"/api/admin-center/inventory/properties/{pid}/").status_code == 204
    assert not VenueProperty.objects.filter(pk=pid).exists()


@pytest.mark.django_db
def test_property_with_spaces_cannot_be_deleted(admin_client, demo_property):
    res = admin_client.delete(f"/api/admin-center/inventory/properties/{demo_property.id}/")
    assert res.status_code == 409


@pytest.mark.django_db
def test_space_create_update_delete_with_audit(admin_client, demo_property):
    payload = {
        "property": str(demo_property.id),
        "name": "Boardroom B",
        "space_type": "BOARDROOM",
        "capacities_json": {"classroom": 20, "u_shape": "14"},
        "rack_rate": "1200.00",
        "base_floor_cost": "800.00",
        "av_capabilities_json": {"screen": True},
    }
    res = admin_client.post("/api/admin-center/inventory/spaces/", payload, format="json")
    assert res.status_code == 201, res.json()
    space = res.json()
    assert space["capacities_json"] == {"classroom": 20, "u_shape": 14}
    assert space["is_booked"] is False

    listed = admin_client.get(f"/api/admin-center/inventory/spaces/?property={demo_property.id}").json()
    assert {s["name"] for s in listed} == {"Grand Ballroom", "Boardroom B"}

    patched = admin_client.patch(
        f"/api/admin-center/inventory/spaces/{space['id']}/", {"rack_rate": "1500.00"}, format="json"
    )
    assert patched.status_code == 200
    assert admin_client.delete(f"/api/admin-center/inventory/spaces/{space['id']}/").status_code == 204
    actions = set(AdminAuditEvent.objects.values_list("action", flat=True))
    assert {"inventory.space.create", "inventory.space.update", "inventory.space.delete"} <= actions


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad",
    [
        {"base_floor_cost": "9000.00"},  # above rack rate
        {"capacities_json": {"stadium": 10}},
        {"capacities_json": {"classroom": -1}},
        {"space_type": "CASTLE"},
    ],
)
def test_space_validation(admin_client, demo_property, bad):
    payload = {
        "property": str(demo_property.id),
        "name": "X",
        "space_type": "BALLROOM",
        "capacities_json": {},
        "rack_rate": "1000.00",
        "base_floor_cost": "500.00",
        **bad,
    }
    res = admin_client.post("/api/admin-center/inventory/spaces/", payload, format="json")
    assert res.status_code == 400
    assert res.json()["detail"]


@pytest.mark.django_db
def test_booked_space_release_then_delete(admin_client, demo_property):
    space = SpaceInventory.objects.get(property=demo_property)
    space.is_booked = True
    space.booking_idempotency_key = "abc"
    space.save()
    url = f"/api/admin-center/inventory/spaces/{space.id}"
    assert admin_client.delete(f"{url}/").status_code == 409
    released = admin_client.post(f"{url}/release/")
    assert released.status_code == 200 and released.json()["is_booked"] is False
    space.refresh_from_db()
    assert space.booking_idempotency_key is None
    assert admin_client.post(f"{url}/release/").status_code == 409
    assert admin_client.delete(f"{url}/").status_code == 204
