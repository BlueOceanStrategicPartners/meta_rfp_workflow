# Template search (agent)

## Prefer hybrid structure search

`search_template` defaults to **mode=hybrid** (not line grep):

1. Build a **structure index** from html / css / js: proposal `<section>` blocks, CSS rules, HTML anchors, JS functions, inline `<style>` / `<script>` in single-file Tailwind proposals.
2. Enrich each symbol with placeholders (`{{…}}`), `data-proposal-*`, and Tailwind `class` tokens from its body.
3. Rank with **hybrid semantic + keyword** scoring (same local embeddings as `list_template_symbols` and agent rules RAG).
4. Return **`symbol_id` + line span** — next step is always `read_template_symbol`, then `replace_lines`.

## When to use each tool

| Intent | Tool |
|--------|------|
| “Find the room block / hero / map section” | `search_template(query=…)` or `list_template_symbols(kind=proposal_section, query=…)` |
| Edit after locate | `read_template_symbol(symbol_id)` → `replace_lines` |
| Exact syntax (`href=`, regex) | `search_template(mode=line)` or `regex=true` |
| Whole file blind read | **Avoid** — wastes tokens |

## Do not

- Loop `search_template` + `read_template_lines` across hundreds of lines.
- Treat truncated line snippets as sufficient context for layout edits.
