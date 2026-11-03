"""Every admin endpoint must reject anyone who is not an ADMIN (spec §6.2, plan §4.3)."""
import re
import uuid

import pytest

from apps.admin_command_center import urls as admin_urls


def _sample_paths():
    for pattern in admin_urls.urlpatterns:
        raw = str(pattern.pattern)
        raw = re.sub(r"\(\?P<[^>]+>[^)]*\)", str(uuid.uuid4()), raw)  # router regex groups first
        raw = re.sub(r"<[^>]+>", str(uuid.uuid4()), raw)  # then path() converters
        raw = raw.lstrip("^").rstrip("$").replace("\\", "")
        yield "/api/admin-center/" + raw


ADMIN_PATHS = sorted(set(_sample_paths())) + [
    "/api/pricing/admin/guardrails/",
    "/api/pricing/admin/retrain/",
]


def test_every_admin_route_is_covered():
    # Guards against a router change silently dropping routes from this matrix.
    assert len(ADMIN_PATHS) >= 25


@pytest.mark.django_db
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_anonymous_is_rejected(api_client, path):
    assert api_client.get(path).status_code in (401, 403)
    assert api_client.post(path, {}, format="json").status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_client_is_forbidden(api_client, client_user, path):
    api_client.force_authenticate(user=client_user)
    assert api_client.get(path).status_code == 403
    assert api_client.post(path, {}, format="json").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_designer_is_forbidden(api_client, designer_user, path):
    api_client.force_authenticate(user=designer_user)
    assert api_client.get(path).status_code == 403
    assert api_client.post(path, {}, format="json").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_admin_is_allowed(admin_client, path):
    assert admin_client.get(path).status_code not in (401, 403)
