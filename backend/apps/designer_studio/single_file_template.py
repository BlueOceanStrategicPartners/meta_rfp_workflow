"""Single-file Tailwind HTML templates (proposal + venue map) — replaces 3-part html/css/js for new work."""
from __future__ import annotations

import re
from typing import Literal

StorageMode = Literal["single", "legacy"]

TAILWIND_CDN_SCRIPT = '<script src="https://cdn.tailwindcss.com"></script>'

PROPOSAL_SINGLE_FILE_SCAFFOLD = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {TAILWIND_CDN_SCRIPT}
  <title>Proposal preview</title>
</head>
<body class="min-h-screen bg-slate-950 text-slate-100 antialiased">
  <header class="border-b border-white/10 px-6 py-4">
    <p class="text-sm uppercase tracking-widest text-cyan-400/90">Hospitality proposal</p>
    <h1 class="mt-1 text-2xl font-semibold">{{{{client_name}}}}</h1>
    <p class="mt-2 text-slate-400">{{{{event_dates}}}}</p>
  </header>
  <main class="mx-auto max-w-5xl space-y-10 px-6 py-10">
    <section class="rounded-2xl border border-white/10 bg-white/5 p-6">
      <h2 class="text-lg font-semibold text-white">Verified room blocks</h2>
      <div class="prose prose-invert mt-4 max-w-none text-sm">{{{{verified_room_blocks}}}}</div>
    </section>
    <section class="rounded-2xl border border-white/10 bg-white/5 p-6">
      <h2 class="text-lg font-semibold">Meeting space</h2>
      <p class="mt-2 text-slate-300">{{{{meeting_space_specs}}}}</p>
    </section>
    <section class="rounded-2xl border border-white/10 bg-white/5 p-6">
      <h2 class="text-lg font-semibold">Investment summary</h2>
      <p class="mt-2 text-slate-300">{{{{xgboost_quote_breakdown}}}}</p>
      <p class="mt-2 text-emerald-300/90">{{{{negotiated_concessions}}}}</p>
    </section>
    <section class="venue-map-proposal rounded-2xl border border-white/10 bg-white/5 p-6" aria-label="Interactive venue map">
      <h2 class="text-lg font-semibold">Venue map</h2>
      <div class="venue-map-root mt-4 min-h-[420px] w-full rounded-xl bg-slate-800/50 p-4" id="venue-map">
        <div class="map-stage relative aspect-[16/10] min-h-[320px] overflow-hidden rounded-lg bg-slate-900/80">
          <img class="map-floorplan absolute inset-0 h-full w-full object-contain opacity-90" alt="Property floorplan" />
          <div class="map-markers pointer-events-none absolute inset-0"></div>
        </div>
        <div id="map-popup" class="map-popup hidden fixed z-50 max-w-sm rounded-xl border border-white/10 bg-slate-950/95 p-4 shadow-xl" role="dialog" aria-hidden="true"></div>
      </div>
    </section>
    <div class="proposal-cta flex flex-wrap gap-3">{{{{cta_accept_button}}}}</div>
  </main>
  <script>
    document.querySelectorAll('a[href^="#"]').forEach(function (link) {{
      link.addEventListener('click', function (e) {{
        var id = link.getAttribute('href').slice(1);
        var el = document.getElementById(id);
        if (el) {{ e.preventDefault(); el.scrollIntoView({{ behavior: 'smooth' }}); }}
      }});
    }});
  </script>
</body>
</html>"""

MAP_SINGLE_FILE_SCAFFOLD = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {TAILWIND_CDN_SCRIPT}
  <title>Venue map</title>
</head>
<body class="bg-slate-900 text-slate-100 p-4">
  <div class="venue-map-root mx-auto max-w-4xl" id="venue-map">
    <div class="map-header mb-3 flex items-baseline justify-between gap-2">
      <h2 class="text-lg font-semibold">Property map</h2>
      <span class="text-xs text-slate-400">Interactive zones</span>
    </div>
    <div class="map-stage relative aspect-[16/10] min-h-[320px] overflow-hidden rounded-xl bg-slate-800/80">
      <img class="map-floorplan absolute inset-0 h-full w-full object-contain opacity-90" alt="Property floorplan" />
      <div class="map-markers pointer-events-none absolute inset-0"></div>
    </div>
    <div id="map-popup" class="map-popup hidden fixed z-50 max-w-sm rounded-xl border border-white/10 bg-slate-950/95 p-4 shadow-xl" role="dialog" aria-hidden="true"></div>
  </div>
  <script>
    /* Map interaction: openLocation, closePopup, postMessage — extend via agent tools */
  </script>
</body>
</html>"""


def template_storage_mode(html: str, css: str = "", js_script: str = "") -> StorageMode:
    """Legacy when css/js columns still hold content; otherwise single-file html_markup."""
    if (css or "").strip() or (js_script or "").strip():
        return "legacy"
    return "single"


def looks_like_full_html_document(text: str) -> bool:
    head = (text or "").lstrip()[:256].lower()
    return head.startswith("<!doctype") or head.startswith("<html")


def extract_inline_styles(html: str) -> str:
    return "\n".join(
        m.group(1) or ""
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", html or "", re.DOTALL | re.IGNORECASE)
    )


def extract_inline_scripts(html: str) -> str:
    return "\n".join(
        m.group(1) or ""
        for m in re.finditer(r"<script[^>]*>(.*?)</script>", html or "", re.DOTALL | re.IGNORECASE)
    )


def ensure_tailwind_cdn(html: str) -> str:
    doc = html or ""
    if "cdn.tailwindcss.com" in doc or "tailwindcss" in doc.lower():
        return doc
    if "</head>" in doc.lower():
        return re.sub(
            r"</head>",
            f"  {TAILWIND_CDN_SCRIPT}\n</head>",
            doc,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"{TAILWIND_CDN_SCRIPT}\n{doc}"


def wrap_fragment_as_single_file(body: str) -> str:
    inner = (body or "").strip()
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">{TAILWIND_CDN_SCRIPT}"
        "</head><body class=\"min-h-screen bg-slate-950 text-slate-100 antialiased\">"
        f"{inner}</body></html>"
    )


def compile_single_file_document(html: str, *, replacements: dict[str, str]) -> str:
    doc = html or ""
    for token, value in replacements.items():
        doc = doc.replace(token, value)
    doc = doc.strip()
    if not doc:
        doc = wrap_fragment_as_single_file(
            '<p class="p-6 text-slate-400">Empty template — chat with the agent to design.</p>'
        )
    elif not looks_like_full_html_document(doc):
        doc = wrap_fragment_as_single_file(doc)
    else:
        doc = ensure_tailwind_cdn(doc)
    return doc


def effective_style_and_script(html: str, css: str, js_script: str) -> tuple[str, str]:
    """CSS/JS text used for validation (single-file inlines + legacy columns)."""
    mode = template_storage_mode(html, css, js_script)
    if mode == "legacy":
        return css or "", js_script or ""
    inline_css = extract_inline_styles(html)
    inline_js = extract_inline_scripts(html)
    return inline_css, inline_js
