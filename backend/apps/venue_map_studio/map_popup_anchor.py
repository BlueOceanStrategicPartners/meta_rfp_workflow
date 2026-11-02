"""Anchor #map-popup near the hovered .map-marker (injected when agent JS omits positioning)."""

MAP_POPUP_ANCHOR_SCRIPT = """
(function mapPopupAnchorBootstrap(){
  if (window.__mapPopupAnchorInstalled) return;
  window.__mapPopupAnchorInstalled = true;

  function positionPopupNearMarker(locationId) {
    var stage = document.querySelector(".map-stage");
    var popup = document.getElementById("map-popup");
    if (!stage || !popup || popup.classList.contains("hidden")) return;
    var marker = stage.querySelector(
      '.map-marker[data-location-id="' + locationId + '"]'
    );
    var pad = 8;
    var gap = 14;
    if (!marker) {
      popup.style.left = pad + "px";
      popup.style.top = pad + "px";
      popup.style.right = "auto";
      popup.style.bottom = "auto";
      return;
    }
    var sw = stage.clientWidth;
    var sh = stage.clientHeight;
    var mr = marker.getBoundingClientRect();
    var sr = stage.getBoundingClientRect();
    var cx = mr.left - sr.left + mr.width / 2;
    var cy = mr.top - sr.top + mr.height / 2;
    var pw = popup.offsetWidth || 280;
    var ph = popup.offsetHeight || 120;
    var left = cx + gap;
    var top = cy - ph / 2;
    if (left + pw > sw - pad) left = cx - pw - gap;
    if (left < pad) left = pad;
    if (top + ph > sh - pad) top = sh - ph - pad;
    if (top < pad) top = pad;
    popup.style.position = "absolute";
    popup.style.left = Math.round(left) + "px";
    popup.style.top = Math.round(top) + "px";
    popup.style.right = "auto";
    popup.style.bottom = "auto";
  }

  window.positionPopupNearMarker = positionPopupNearMarker;

  function resolveActiveLocationId() {
    var active = document.querySelector(".map-marker.is-active[data-location-id]");
    if (active) return active.getAttribute("data-location-id");
    active = document.querySelector(".map-zone-row.is-active[data-location-id]");
    if (active) return active.getAttribute("data-location-id");
    return null;
  }

  function repositionIfOpen() {
    var popup = document.getElementById("map-popup");
    if (!popup || popup.classList.contains("hidden")) return;
    var id = resolveActiveLocationId();
    if (id) requestAnimationFrame(function () { positionPopupNearMarker(id); });
  }

  var popupEl = document.getElementById("map-popup");
  if (popupEl) {
    new MutationObserver(repositionIfOpen).observe(popupEl, {
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  document.addEventListener(
    "mouseover",
    function (e) {
      var marker = e.target.closest && e.target.closest(".map-marker[data-location-id]");
      if (!marker) return;
      var id = marker.getAttribute("data-location-id");
      requestAnimationFrame(function () {
        var p = document.getElementById("map-popup");
        if (p && !p.classList.contains("hidden")) positionPopupNearMarker(id);
      });
    },
    true
  );

  window.addEventListener("resize", repositionIfOpen);
})();
""".strip()

MAP_POPUP_ANCHOR_CSS = """
.map-popup{position:absolute;top:0;left:0;right:auto;bottom:auto;max-width:min(320px,88%);pointer-events:auto;}
""".strip()
