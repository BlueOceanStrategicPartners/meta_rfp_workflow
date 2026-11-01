# Designing Studio — UI/UX Audit & Improvement Backlog

**Status:** Core features implemented; layout polish pass (2026-11-02).

## Layout & visual polish (2026-11-02)

| Issue | Fix |
|-------|-----|
| Search / footer fields clipped at panel top | Shared `--studio-inset-x`, `studio-panel-body` / `studio-panel-footer` with `pt-5` / `pb-6` |
| Default white scrollbars | `.studio-scroll` thin dark thumb on template list, chat, tokens, revisions |
| Cramped composer | `.studio-composer` padding, aligned `min-h-[2.75rem]` controls, icon labels |
| Token footer unreadable | Click-to-copy chip buttons instead of single-line scroll text |
| Template footer hierarchy | Labeled “Template name”, destructive Delete styling, consistent `studio-btn-secondary` |
| Inconsistent horizontal padding | Panels use `var(--studio-inset-x)` instead of mixed `px-3` / `px-5` |

| Token footer removed | RFP bindings enforced by Muse Spark server-side only (`Docs/Designer_Studio_Muse_Spark_Contract.md`) |
| Studio sub-header removed | Logout + theme in app nav; no Muse/Fixture badges in UI |
| Save label | **Save template** (validate on save via API) |
| Preview check | **Check template** (not “Validate (Spark)”) |

## Optional follow-ups (not blocking)

- Replace emoji icons with SVG for Attach / Voice / Search
- Collapse empty-state drag hint after first upload (persist preference)
- Token chips: toast on copy instead of sr-only only
- Preview header: merge into `studio-panel-header` for one rhythm with chat/library

## Implemented features

| ID | Feature | Layer |
|----|---------|--------|
| UX-07 | Per-file upload progress (XHR + progress bars) | Frontend |
| UX-08 | Media library drawer | Frontend |
| UX-09 | Agent clarification chips | Frontend + Spark JSON |
| — | Message timestamps & role labels | Frontend + API `ts` on history |
| — | Regenerate last prompt | Frontend |
| — | Undo last layout (snapshot stack) | Frontend |
| — | Export chat + template JSON | Frontend + `GET .../export/` |
| — | @mention assets in composer | Frontend |
| — | Markdown in assistant messages | `designerMarkdown.ts` |
| — | Fixture vs Live Muse badge | Frontend (`used_fixture`) |
| — | Logout in studio header | Frontend + `/api/auth/logout/` |
| — | Preview breakpoints + fullscreen + new tab | Frontend |
| — | Duplicate / delete template | Frontend + API |
| — | Version history + restore | Backend `revision_history_json` + restore API |
| — | Template search | Frontend |
| — | Missing placeholder highlight | Frontend (sample inject off) |
| — | Clear chat confirm modal | Frontend |
| — | Pin messages | Frontend |
| — | Voice input (Web Speech API) | Frontend |
| — | Keyboard shortcut help (`?`) | Frontend |
| — | Focus rings + reduced motion | `index.css` |
| — | Screen reader live region | Frontend `aria-live` |

## API routes added

- `POST /api/designer/templates/<id>/duplicate/`
- `POST /api/designer/templates/<id>/restore-revision/` `{ "index": 0 }`
- `GET /api/designer/templates/<id>/export/`

## Files

- `frontend/src/pages/DesignerPortal.tsx` — integrated studio
- `frontend/src/components/designer/*` — chat, dialogs, library
- `frontend/src/lib/designerApi.ts`, `designerUpload.ts`, `designerMarkdown.ts`
- `backend/apps/designer_studio/revisions.py`, migration `0003_revision_history`
