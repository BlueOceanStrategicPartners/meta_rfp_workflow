/** Block srcdoc proposal iframes from navigating into the host SPA (/client, /designer, …). */

export const PROPOSAL_EMBED_NAV_GUARD_MARKER = "data-proposal-embed-nav-guard";

export const PROPOSAL_EMBED_NAV_GUARD_SCRIPT = `<script ${PROPOSAL_EMBED_NAV_GUARD_MARKER}>
(function(){
  var APP_PATH = /^\\/(client|designer|admin)(\\/|$)/;
  function appPathname(path) {
    try { return APP_PATH.test(path || ''); } catch (e) { return false; }
  }
  function slugFromPath(path) {
    var core = String(path || '').split('?')[0].split('#')[0].replace(/^\\/+|\\/+$/g, '') || 'top';
    return core.replace(/\\//g, '-');
  }
  function elementDocumentY(el) {
    var y = 0;
    var node = el;
    while (node) {
      y += node.offsetTop || 0;
      node = node.offsetParent;
    }
    return y;
  }
  function notifyParentScroll(el) {
    try {
      if (!el || !window.parent || window.parent === window) return;
      var top = elementDocumentY(el);
      var margin = 0;
      try {
        var st = window.getComputedStyle(el);
        margin = parseFloat(st.scrollMarginTop || '0') || 0;
      } catch (e) {}
      window.parent.postMessage(
        { type: 'proposal-embed-scroll', top: Math.max(0, Math.round(top - margin)), behavior: 'smooth' },
        '*'
      );
    } catch (e) {}
  }
  function scrollToInPageTarget(href) {
    var h = String(href || '').trim();
    if (!h) return false;
    var hash = '';
    if (h.charAt(0) === '#') {
      hash = h.slice(1);
    } else {
      try {
        var u = new URL(h, window.location.href);
        if (u.hash && u.hash.length > 1) hash = u.hash.slice(1);
        else hash = slugFromPath(u.pathname);
      } catch (e) {
        return false;
      }
    }
    if (!hash) return false;
    var el =
      document.getElementById(hash) ||
      document.querySelector('[name="' + hash.replace(/"/g, '') + '"]');
    if (!el) {
      var lower = hash.toLowerCase();
      var nodes = document.querySelectorAll('section[id], main [id], [id]');
      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].id && nodes[i].id.toLowerCase() === lower) {
          el = nodes[i];
          break;
        }
      }
    }
    if (el) {
      notifyParentScroll(el);
      if (el.scrollIntoView) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      return true;
    }
    return false;
  }
  function normalizeAnchors() {
    document.querySelectorAll('a[href]').forEach(function(el) {
      el.setAttribute('target', '_self');
      el.removeAttribute('rel');
      var href = (el.getAttribute('href') || '').trim();
      if (href.charAt(0) === '/') {
        var slug = slugFromPath(href);
        el.setAttribute('href', '#' + slug);
      } else if (/^https?:\\/\\//i.test(href)) {
        try {
          var u = new URL(href, window.location.href);
          if (u.origin === window.top.location.origin && (appPathname(u.pathname) || u.pathname.indexOf('/') === 0)) {
            el.setAttribute('href', u.hash || ('#' + slugFromPath(u.pathname)));
          }
        } catch (e) {}
      }
    });
    document.querySelectorAll('form[action]').forEach(function(el) {
      try {
        var action = el.getAttribute('action') || '';
        if (action.charAt(0) === '/' && appPathname(action.split('?')[0])) {
          el.setAttribute('action', '#');
        }
      } catch (e) {}
    });
  }
  function shouldBlockHref(href) {
    if (!href) return false;
    var h = href.trim();
    if (!h || h.charAt(0) === '#') return false;
    if (/^(mailto:|tel:|javascript:)/i.test(h)) return false;
    if (/^https?:\\/\\//i.test(h)) {
      try {
        var u = new URL(h, window.location.href);
        if (u.origin === window.top.location.origin && appPathname(u.pathname)) return true;
        if (u.origin === window.top.location.origin && u.pathname.charAt(0) === '/') return true;
      } catch (e) { return true; }
      return false;
    }
    if (h.charAt(0) === '/') return true;
    return true;
  }
  function onNavigateAttempt(href, e) {
    if (!shouldBlockHref(href)) return false;
    if (e) { e.preventDefault(); e.stopPropagation(); }
    if (/^https?:\\/\\//i.test(href)) {
      try {
        var ext = new URL(href, window.location.href);
        if (ext.origin !== window.top.location.origin) {
          window.open(href, '_blank', 'noopener,noreferrer');
          return true;
        }
      } catch (err) {}
    }
    scrollToInPageTarget(href);
    return true;
  }
  document.addEventListener('click', function(e) {
    var el = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!el) return;
    var href = (el.getAttribute('href') || '').trim();
    if (shouldBlockHref(href)) {
      onNavigateAttempt(href, e);
      return;
    }
    if (href.charAt(0) === '#') {
      e.preventDefault();
      scrollToInPageTarget(href);
    }
  }, true);
  document.addEventListener('submit', function(e) {
    var form = e.target;
    if (!form || !form.getAttribute) return;
    var action = (form.getAttribute('action') || '').trim();
    if (action && shouldBlockHref(action)) {
      e.preventDefault();
      e.stopPropagation();
      scrollToInPageTarget(action);
    }
  }, true);
  try {
    var loc = window.location;
    var assign = loc.assign.bind(loc);
    var replace = loc.replace.bind(loc);
    loc.assign = function(url) {
      if (onNavigateAttempt(String(url || ''), null)) return;
      return assign(url);
    };
    loc.replace = function(url) {
      if (onNavigateAttempt(String(url || ''), null)) return;
      return replace(url);
    };
  } catch (e) {}
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', normalizeAnchors);
  } else {
    normalizeAnchors();
  }
})();
</script>`;

/** Root-relative hrefs in srcdoc resolve against the host app — rewrite to in-page anchors. */
export function sanitizePreviewDocumentLinks(doc: string): string {
  const slugFromPath = (path: string) => {
    const core = path.split("?")[0].split("#")[0].replace(/^\/+|\/+$/g, "") || "top";
    return core.replace(/\//g, "-");
  };
  let out = doc;
  out = out.replace(/\bhref\s*=\s*(["'])(\/[^"'#][^"']*)\1/gi, (_m, q: string, path: string) => {
    return `href=${q}#${slugFromPath(path)}${q}`;
  });
  out = out.replace(/\baction\s*=\s*(["'])(\/(?:client|designer|admin)[^"']*)\1/gi, (_m, q: string) => {
    return `action=${q}#${q}`;
  });
  return out;
}

export function appendProposalEmbedNavGuard(doc: string): string {
  if (!doc || doc.includes(PROPOSAL_EMBED_NAV_GUARD_MARKER)) return doc;
  if (doc.includes("</body>")) {
    return doc.replace("</body>", `${PROPOSAL_EMBED_NAV_GUARD_SCRIPT}</body>`);
  }
  return `${doc}${PROPOSAL_EMBED_NAV_GUARD_SCRIPT}`;
}

/** Sanitize links + inject in-iframe nav guard (designer live preview + client proposal embed). */
export function isolateProposalEmbedNavigation(doc: string): string {
  return appendProposalEmbedNavGuard(sanitizePreviewDocumentLinks(doc));
}

export function proposalEmbedDocumentIsActive(doc: Document | null | undefined): boolean {
  if (!doc) return false;
  return Boolean(doc.querySelector(`[${PROPOSAL_EMBED_NAV_GUARD_MARKER}]`));
}
