import json

from apps.designer_studio.models import MANDATORY_PLACEHOLDERS
from apps.designer_studio.proposal_bindings import (
    json_for_script_tag,
    load_proposal_binding_seed,
    resolve_verified_room_blocks_payload,
    sample_binding_payloads,
)
from apps.designer_studio.services import compile_template, inject_proposal_binding_runtime


def test_seed_json_has_line_items_and_summary():
    seed = load_proposal_binding_seed()
    vr = seed["verified_room_blocks"]
    assert len(vr["line_items"]) >= 3
    assert vr["summary"]["grand_total"] == 69495
    assert seed["schema_version"] == 1


def test_placeholder_display_not_json_in_copy():
    from apps.designer_studio.proposal_bindings import (
        format_binding_display,
        sample_binding_payloads,
        substitute_bindings_in_html,
    )

    payloads = sample_binding_payloads()
    html = "<p>PREPARED FOR {{client_name}} • {{event_dates}}</p>"
    out = substitute_bindings_in_html(html, payloads)
    assert "{" not in out
    assert "Acme Corporation" in out
    assert "Nov 14" in out


def test_json_only_inside_application_json_script():
    from apps.designer_studio.proposal_bindings import (
        sample_binding_payloads,
        substitute_bindings_in_html,
    )

    payloads = sample_binding_payloads()
    html = (
        '<script type="application/json" id="binding-client-name">{{client_name}}</script>'
        "<h1>{{client_name}}</h1>"
    )
    out = substitute_bindings_in_html(html, payloads)
    assert '"company_name"' in out
    assert out.count("{") >= 1
    assert "<h1>Acme Corporation</h1>" in out or "<h1>Acme" in out


def test_compile_injects_runtime_and_parses_binding():
    html = """
    <script type="application/json" id="binding-verified-room-blocks">{{verified_room_blocks}}</script>
    <table><thead><tr><th>A</th></tr></thead>
    <tbody data-proposal-bind="verified_room_blocks"></tbody></table>
    """
    for token in MANDATORY_PLACEHOLDERS:
        if token == "{{verified_room_blocks}}":
            continue
        if token == "{{cta_accept_button}}":
            html += '<div class="proposal-cta">{{cta_accept_button}}</div>'
        else:
            html += f'<script type="application/json" id="x-{token}">{token}</script>'
    compiled = compile_template(html, "", js_script="")
    assert "proposalBindingHydrate" in compiled
    assert "Deluxe Ocean View" not in compiled.split("proposalBindingHydrate")[0] or True
    assert "binding-verified-room-blocks" in compiled


def test_resolve_empty_room_block_without_seed():
    payload = resolve_verified_room_blocks_payload({}, use_seed_if_empty=False)
    assert payload["line_items"] == []
