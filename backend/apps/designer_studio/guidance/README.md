# Designer Studio — prompt guidance (Markdown)

Edit these files to change what the **design agent**, **tool-loop editor**, and **validation** models are told about proposal placeholders. Python loads them at runtime (cached until process restart).

| File | Used by |
|------|---------|
| `placeholder_binding.md` | Design agent, repair agent, tool-loop system prompt |
| `placeholder_validation.md` | Chat validation, save validation, Muse layout review |
| `proposal_binding_schema.md` | **Agent knowledge**: JSON types, arrays vs lists, column fields, default vs user override |
| `template_search.md` | **Hybrid structure search**: `search_template` vs line grep, symbol_id workflow |
| `proposal_binding_seed.json` | Canonical JSON seed for all binding structures |
| `proposal_binding_runtime.js` | Client-side hydrate (tables from JSON) |

## Dynamic token

`{{MANDATORY_PLACEHOLDERS_LIST}}` in any guidance file is replaced with the canonical list from `apps.designer_studio.models.MANDATORY_PLACEHOLDERS` (same list the API enforces on save).

## After editing

- Restart the Django dev server so `@lru_cache` reloads guidance (or deploy a new worker).
- Run `pytest backend/tests/test_placeholder_guidance.py` to confirm files load and expand.

Do not put secrets or environment-specific URLs in these files.
