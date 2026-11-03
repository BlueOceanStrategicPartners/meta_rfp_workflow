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


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        username="admin1",
        email="admin@example.com",
        password="pass12345",
        role="ADMIN",
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def demo_property():
    from apps.inventory.models import SpaceInventory, VenueProperty

    prop = VenueProperty.objects.create(name="Test Hotel")
    SpaceInventory.objects.create(
        property=prop,
        name="Grand Ballroom",
        space_type="BALLROOM",
        capacities_json={"classroom": 250, "banquet": 400},
        rack_rate=8500,
        base_floor_cost=6000,
    )
    return prop


@pytest.fixture
def seeded_rfp(client_user, demo_property):
    """An RFP pushed through the real pipeline in fixture mode (ends NEGOTIATING with a quote)."""
    from apps.rfp_debate.models import RFPSubmission
    from apps.rfp_debate.tasks import run_debate_pipeline

    rfp = RFPSubmission.objects.create(
        client=client_user, source_document_text="Acme summit, 3 nights, 200 guests classroom."
    )
    run_debate_pipeline(str(rfp.id))
    rfp.refresh_from_db()
    _move_to_future(rfp)
    return rfp


def _move_to_future(rfp):
    from datetime import date, timedelta

    start = date.today() + timedelta(days=30)
    cards = dict(rfp.active_ui_cards_json or {})
    overview = dict(cards.get("event_overview") or {})
    overview["check_in_date"] = start.isoformat()
    overview["check_out_date"] = (start + timedelta(days=3)).isoformat()
    cards["event_overview"] = overview
    rfp.active_ui_cards_json = cards
    rfp.save(update_fields=["active_ui_cards_json"])
