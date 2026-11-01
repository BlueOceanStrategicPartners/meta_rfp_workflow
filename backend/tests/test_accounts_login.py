import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_studio_demo_login_returns_jwt(api_client, designer_user):
    api_client.force_authenticate(user=None)
    from apps.accounts_rbac.demo_accounts import ensure_studio_demo_user

    ensure_studio_demo_user(reset_password=True)
    res = api_client.post(
        "/api/auth/login/",
        {"email": "designer@demo.local", "password": "demo12345"},
        format="json",
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access"]
    assert body["refresh"]
    me = api_client.get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION=f"Bearer {body['access']}",
    )
    assert me.json()["authenticated"] is True


@pytest.mark.django_db
def test_studio_demo_login_provisions_user(settings):
    settings.DEBUG = True
    from apps.accounts_rbac.models import CustomUser

    CustomUser.objects.filter(email="designer@demo.local").delete()

    client = Client(HTTP_HOST="127.0.0.1")
    res = client.post(
        "/api/auth/login/",
        data=json.dumps(
            {"email": "designer@demo.local", "password": "demo12345"},
        ),
        content_type="application/json",
    )
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "DESIGNER"
    assert CustomUser.objects.filter(email="designer@demo.local").exists()


@pytest.mark.django_db
def test_studio_login_rejects_wrong_password(settings):
    settings.DEBUG = True
    from apps.accounts_rbac.demo_accounts import ensure_studio_demo_user

    ensure_studio_demo_user(reset_password=True)
    client = Client(HTTP_HOST="127.0.0.1")
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"email": "designer@demo.local", "password": "not-demo"}),
        content_type="application/json",
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]
