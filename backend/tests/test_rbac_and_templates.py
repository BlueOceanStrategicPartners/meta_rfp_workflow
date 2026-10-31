import pytest
from apps.designer_studio.models import ProposalTemplate


@pytest.mark.django_db
def test_only_one_default_template(designer_user):
    ProposalTemplate.objects.create(
        name="A",
        designer=designer_user,
        html_markup="{{client_name}}",
        is_default=True,
    )
    t2 = ProposalTemplate(
        name="B",
        designer=designer_user,
        html_markup="{{client_name}}",
        is_default=True,
    )
    t2.save()
    assert ProposalTemplate.objects.filter(is_default=True).count() == 1
    assert ProposalTemplate.objects.get(is_default=True).name == "B"


@pytest.mark.django_db
def test_designer_cannot_access_admin_pricing_guardrails(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    response = api_client.get("/api/pricing/admin/guardrails/")
    assert response.status_code == 403
