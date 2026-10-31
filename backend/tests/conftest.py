import pytest


@pytest.fixture(scope="session", autouse=True)
def _test_settings():
    from django.conf import settings

    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.USE_FIXTURE_DEBATE = True
    settings.USE_SEAMLESS_FIXTURE = True


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def client_user(django_user_model):
    return django_user_model.objects.create_user(
        username="client1",
        email="client@example.com",
        password="pass12345",
        role="CLIENT",
    )


@pytest.fixture
def designer_user(django_user_model):
    return django_user_model.objects.create_user(
        username="designer1",
        email="designer@example.com",
        password="pass12345",
        role="DESIGNER",
    )


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        username="admin1",
        email="admin@example.com",
        password="pass12345",
        role="ADMIN",
    )
