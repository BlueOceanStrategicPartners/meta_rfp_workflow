## Proposal placeholders — quick rules

Full **JSON schema knowledge** for the design agent: **`proposal_binding_schema.md`** (read that for arrays, columns, lists, defaults vs user overrides).

Mandatory tokens: {{MANDATORY_PLACEHOLDERS_LIST}}

- Placeholders compile to **JSON** inside `<script type="application/json" id="binding-…">` — **not** pre-built HTML tables.
- **`verified_room_blocks`**: `line_items[]` = table **rows**; `summary` = footer totals; empty `<tbody data-proposal-bind="verified_room_blocks">`.
- **`negotiated_concessions`**: `{ "items": [ … ] }` **list**.
- Include `proposal_binding_runtime.js` once unless the user opts out and writes their own parser.
- Seed file: `samples/proposal_binding_seed.json`.

See **`proposal_binding_schema.md`** for field-to-column mapping and greenfield scaffold.
