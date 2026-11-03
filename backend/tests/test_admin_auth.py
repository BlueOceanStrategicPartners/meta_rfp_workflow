import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator

from apps.accounts_rbac.demo_accounts import ensure_admin_demo_user


@pytest.mark.django_db
def test_demo_admin_login_returns_admin_role_and_jwt(api_client):
    ensure_admin_demo_user(reset_password=True)
    res = api_client.post(
        "/api/auth/login/",
        {"email": "admin@demo.local", "password": "admin12345"},
        format="json",
    )
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "ADMIN"
    me = api_client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert me.json()["role"] == "ADMIN"
    overview = api_client.get(
        "/api/admin-center/overview/", HTTP_AUTHORIZATION=f"Bearer {body['access']}"
    )
    assert overview.status_code == 200


@pytest.mark.django_db
def test_demo_admin_is_provisioned_in_debug(api_client, settings):
    settings.DEBUG = True
    res = api_client.post(
        "/api/auth/login/",
        {"email": "admin@demo.local", "password": "admin12345"},
        format="json",
    )
    assert res.status_code == 200
    assert res.json()["role"] == "ADMIN"


@pytest.mark.django_db
def test_wrong_admin_password_is_rejected(api_client):
    ensure_admin_demo_user(reset_password=True)
    res = api_client.post(
        "/api/auth/login/", {"email": "admin@demo.local", "password": "nope"}, format="json"
    )
    assert res.status_code == 401


def _connect(user):
    from apps.admin_command_center.consumers import AdminTelemetryConsumer

    communicator = WebsocketCommunicator(AdminTelemetryConsumer.as_asgi(), "/ws/admin/telemetry/")
    communicator.scope["user"] = user

    async def run():
        connected, code = await communicator.connect()
        await communicator.disconnect()
        return connected, code

    return async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
def test_telemetry_socket_rejects_non_admin(client_user):
    connected, code = _connect(client_user)
    assert connected is False
    assert code == 4403


@pytest.mark.django_db(transaction=True)
def test_telemetry_socket_accepts_admin(admin_user):
    connected, _ = _connect(admin_user)
    assert connected is True
