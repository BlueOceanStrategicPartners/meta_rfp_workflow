import pytest

from apps.designer_studio.agent_rules import (
    embed_rule_text,
    hybrid_score,
    tokenize,
    validate_rule_conflict,
)
from apps.designer_studio.models import DesignerAgentRule


@pytest.mark.django_db
def test_embed_and_hybrid_prefers_related_rule(designer_user):
    a = DesignerAgentRule.objects.create(
        designer=designer_user,
        body="Always use dark mode luxury theme with gold accents.",
        embedding_json=embed_rule_text("Always use dark mode luxury theme with gold accents."),
        search_tokens_json=tokenize("Always use dark mode luxury theme with gold accents."),
    )
    b = DesignerAgentRule.objects.create(
        designer=designer_user,
        body="Never hide the accept CTA on desktop breakpoints.",
        embedding_json=embed_rule_text("Never hide the accept CTA on desktop breakpoints."),
        search_tokens_json=tokenize("Never hide the accept CTA on desktop breakpoints."),
    )
    q_tokens = set(tokenize("fix dark theme hero and CTA visibility"))
    score_a = hybrid_score(embed_rule_text("fix dark theme hero"), q_tokens, a)
    score_b = hybrid_score(embed_rule_text("fix dark theme hero"), q_tokens, b)
    assert score_a > score_b


@pytest.mark.django_db
def test_list_agent_rules_empty(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    response = api_client.get("/api/designer/agent-rules/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_fixture_rule_conflict_detects_opposing_modes(designer_user):
    DesignerAgentRule.objects.create(
        designer=designer_user,
        body="Always use light mode editorial layout.",
    )
    result = validate_rule_conflict(
        designer_id=designer_user.id,
        new_body="Always use dark mode for the proposal shell.",
    )
    assert result["has_conflict"] is True
    assert result["suggested_rule"]
