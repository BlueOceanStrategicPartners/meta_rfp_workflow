from apps.designer_studio.map_interaction_normalize import normalize_map_interaction


def test_normalize_adds_hidden_to_map_popup():
    html = "<div id='map-popup' class='map-popup'></div>"
    css = ".map-popup{position:fixed;inset:20%;}"
    js = "function showPopup(){document.getElementById('map-popup').classList.remove('hidden');}"
    h, c, j = normalize_map_interaction(html, css, js)
    assert "hidden" in h
    assert "closePopup" in j
    assert "mapPopupAnchorBootstrap" in j or "positionPopupNearMarker" in j
