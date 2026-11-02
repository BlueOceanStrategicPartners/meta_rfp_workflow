from apps.venue_map_studio.map_markup_guard import (
    extract_interactive_map_markup,
    looks_like_proposal_body,
    normalize_map_record_markup,
)


def test_extracts_venue_map_root():
    html = (
        "<header>Proposal junk</header>"
        "<div class='venue-map-root' id='venue-map'>"
        "<img class='floorplan' src='/x.png'/>"
        "<button data-location-id='a'>A</button>"
        "</div>"
        "<footer>CTA</footer>"
    )
    out = extract_interactive_map_markup(html)
    assert out.startswith("<div class='venue-map-root'")
    assert "header" not in out.lower()
    assert "footer" not in out.lower()


def test_proposal_only_returns_empty():
    html = "<header class='hero'><h1>{{client_name}}</h1></header><main>{{selected_map_svg}}</main>"
    assert extract_interactive_map_markup(html) == ""


def test_normalize_strips_proposal_wrapper():
    html = (
        "<section class='venue-map-proposal'>"
        "<div class='venue-map-root'><button data-location-id='z'>Z</button></div>"
        "</section>"
    )
    cleaned, warnings = normalize_map_record_markup(html)
    assert "venue-map-root" in cleaned
    assert "{{" not in cleaned
    assert warnings


def test_looks_like_proposal_body():
    assert looks_like_proposal_body("{{client_name}} hero")
    assert not looks_like_proposal_body("<div class='venue-map-root'></div>")
