/**
 * Proposal binding runtime — sync with backend/apps/designer_studio/samples/proposal_binding_runtime.js
 */
(function () {
  function money(n) {
    if (n == null || n === "") return "—";
    var x = Number(n);
    if (!isFinite(x)) return String(n);
    return x % 1 === 0 ? "$" + x.toLocaleString("en-US") : "$" + x.toFixed(2);
  }

  function readBinding(id) {
    var el = document.getElementById(id);
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.warn("proposal binding parse failed:", id, e);
      return null;
    }
  }

  function renderRoomBlockTable(data) {
    if (!data) return;
    var tbody = document.querySelector('[data-proposal-bind="verified_room_blocks"]');
    if (!tbody) return;
    var items = data.line_items || [];
    var summary = data.summary || {};
    var html = "";
    items.forEach(function (item) {
      var badge = item.badge
        ? ' <span class="room-block-badge">' + escapeHtml(item.badge) + "</span>"
        : "";
      var sub = item.category_subtitle
        ? '<div class="text-xs opacity-70">' + escapeHtml(item.category_subtitle) + "</div>"
        : "";
      html +=
        "<tr>" +
        '<td class="room-block-category"><div class="font-medium">' +
        escapeHtml(item.category_name || "") +
        badge +
        "</div>" +
        sub +
        "</td>" +
        '<td class="room-block-dates">' +
        escapeHtml(item.date_range || "") +
        "</td>" +
        '<td class="room-block-nights">' +
        (item.nights != null ? item.nights : "") +
        "</td>" +
        '<td class="room-block-qty">' +
        (item.quantity != null ? item.quantity : "") +
        "</td>" +
        '<td class="room-block-rate">' +
        money(item.rate_per_night) +
        "</td>" +
        '<td class="room-block-total">' +
        money(item.estimated_total) +
        "</td>" +
        "</tr>";
    });
    if (summary && (summary.grand_total || summary.rooms_per_night)) {
      var label =
        "Total block — " +
        (summary.rooms_per_night || "—") +
        " rooms × " +
        (summary.nights || "—") +
        " nights (" +
        (summary.room_nights || "—") +
        " room-nights)";
      html +=
        '<tr class="room-block-total-row">' +
        "<td colspan=\"2\">" +
        escapeHtml(label) +
        "</td>" +
        '<td class="room-block-nights">' +
        (summary.nights != null ? summary.nights : "—") +
        "</td>" +
        '<td class="room-block-qty">' +
        (summary.rooms_per_night != null ? summary.rooms_per_night + " / night" : "—") +
        "</td>" +
        '<td class="room-block-rate">Avg ' +
        money(summary.avg_rate_per_night) +
        "</td>" +
        '<td class="room-block-total">' +
        money(summary.grand_total) +
        "</td></tr>";
    }
    if (summary.policy_notes) {
      html +=
        '<tr class="room-block-policy-row"><td colspan="6" class="text-xs opacity-80">' +
        escapeHtml(summary.policy_notes) +
        "</td></tr>";
    }
    tbody.innerHTML = html;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function hydrateTextTargets() {
    var dates = readBinding("binding-event-dates");
    if (dates && dates.display_range) {
      document.querySelectorAll('[data-proposal-field="event_dates"]').forEach(function (el) {
        el.textContent = dates.display_range;
      });
    }
    var client = readBinding("binding-client-name");
    if (client && client.company_name) {
      document.querySelectorAll('[data-proposal-field="client_name"]').forEach(function (el) {
        el.textContent = client.company_name || "";
      });
    }
    var meeting = readBinding("binding-meeting-space");
    if (meeting) {
      var meetingText = [
        meeting.name,
        meeting.seating_style,
        meeting.headcount ? meeting.headcount + " guests" : "",
        meeting.av,
      ]
        .filter(Boolean)
        .join(" · ");
      document.querySelectorAll('[data-proposal-field="meeting_space_specs"]').forEach(function (el) {
        el.textContent = meetingText;
      });
    }
    var quote = readBinding("binding-xgboost-quote");
    if (quote) {
      var quoteParts = [];
      if (quote.walk_away_floor_price != null) {
        quoteParts.push("Floor " + money(quote.walk_away_floor_price));
      }
      if (quote.optimal_target_price != null) {
        quoteParts.push("Target " + money(quote.optimal_target_price));
      }
      if (quote.initial_anchor_price != null) {
        quoteParts.push("Anchor " + money(quote.initial_anchor_price));
      }
      var quoteText = quoteParts.join(" · ");
      document.querySelectorAll('[data-proposal-field="xgboost_quote_breakdown"]').forEach(function (el) {
        el.textContent = quoteText;
      });
    }
    var neg = readBinding("binding-negotiated-concessions");
    if (neg && neg.items && neg.items.length) {
      var listText = neg.items.join(" · ");
      document.querySelectorAll('[data-proposal-field="negotiated_concessions"]').forEach(function (el) {
        el.textContent = listText;
      });
    }
  }

  window.proposalBindingHydrate = function () {
    renderRoomBlockTable(readBinding("binding-verified-room-blocks"));
    hydrateTextTargets();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", window.proposalBindingHydrate);
  } else {
    window.proposalBindingHydrate();
  }
})();
