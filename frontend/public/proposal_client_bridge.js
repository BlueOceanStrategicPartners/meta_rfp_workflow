/**
 * Client proposal bridge — emits structured events to the parent ClientWorkspace.
 * Include once in proposal html (compile may inject inline for client render).
 */
(function () {
  function postToParent(payload) {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(payload, "*");
      }
    } catch (e) {
      console.warn("proposal client bridge:", e);
    }
  }

  window.rfpProposalEmit = function (detail) {
    if (!detail || typeof detail !== "object") return;
    postToParent({
      type: "rfp-proposal-event",
      kind: detail.kind || detail.type || "event",
      action: String(detail.action || "interaction"),
      label: String(detail.label || detail.action || "Proposal interaction").slice(0, 200),
      cardPatch: detail.cardPatch || detail.card_patch || null,
      meta: detail.meta && typeof detail.meta === "object" ? detail.meta : {},
    });
  };

  function readValue(el) {
    if (!el) return "";
    if (el.type === "number" || el.type === "range") {
      var n = Number(el.value);
      return Number.isFinite(n) ? n : el.value;
    }
    return el.value;
  }

  function buildPatchFromPath(path, value) {
    var parts = String(path || "").split(".");
    if (parts.length !== 2) return null;
    var patch = {};
    var inner = {};
    inner[parts[1]] = value;
    patch[parts[0]] = inner;
    return patch;
  }

  function patchFromElement(mutationPath, el) {
    var valueFrom = el.getAttribute("data-proposal-value-from");
    if (valueFrom) {
      var target = document.querySelector(valueFrom);
      if (target) return buildPatchFromPath(mutationPath, readValue(target));
    }
    return buildPatchFromPath(mutationPath, readValue(el));
  }

  function wireDeclarativeControls() {
    document.querySelectorAll("[data-proposal-action]").forEach(function (el) {
      if (el.__rfpBridgeWired) return;
      el.__rfpBridgeWired = true;
      el.addEventListener("click", function () {
        var action = el.getAttribute("data-proposal-action") || "click";
        var label = (el.getAttribute("data-proposal-label") || el.textContent || action)
          .trim()
          .slice(0, 200);
        if (action === "accept" || action === "accept_proposal") {
          window.rfpProposalEmit({
            kind: "event",
            action: "accept_proposal",
            label: label || "Accept proposal",
          });
          return;
        }
        var mutationPath = el.getAttribute("data-proposal-mutation");
        if (mutationPath) {
          var patch = patchFromElement(mutationPath, el);
          if (patch) {
            window.rfpProposalEmit({
              kind: "mutation",
              action: action,
              label: label,
              cardPatch: patch,
            });
          }
          return;
        }
        window.rfpProposalEmit({
          kind: "event",
          action: action,
          label: label,
          meta: { section: el.getAttribute("data-proposal-section") || "" },
        });
      });
    });

    document.querySelectorAll("[data-proposal-mutation]").forEach(function (el) {
      if (el.__rfpMutationWired || el.getAttribute("data-proposal-action")) return;
      el.__rfpMutationWired = true;
      el.addEventListener("change", function () {
        var path = el.getAttribute("data-proposal-mutation");
        var patch = buildPatchFromPath(path, readValue(el));
        if (patch) {
          window.rfpProposalEmit({
            kind: "mutation",
            action: "field_change",
            label: "Updated " + path,
            cardPatch: patch,
          });
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireDeclarativeControls);
  } else {
    wireDeclarativeControls();
  }
})();
