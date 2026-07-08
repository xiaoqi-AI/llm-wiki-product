# llm-wiki Product Architecture

## Goal

Turn a private Markdown knowledge base into a continuously improvable local knowledge product with a clear split between source, generated data, and frontend features.

## Layers

### Private Knowledge Source

The source of truth stays outside the public repository. During local use it can live in an ignored `wiki/` directory or any private directory passed through `--wiki-dir`.

The frontend should not parse or traverse the private source tree directly.

### Data Product

`tools/build-wiki-product.py` scans a private Markdown source tree and emits stable frontend data packages under ignored `public/data/`. Existing graph exports can seed relationship edges, but the source of truth is the private Markdown knowledge base:

- `meta.json`: build metadata, counts, top tags, warning counts.
- `graph-data.json`: graph nodes and edges without full markdown bodies.
- `search-index.json`: searchable pages with extracted metadata and compact body-search text.
- `project-index.json`: project dashboard data.
- `topic-index.json`: topic dashboard data.
- `recent-index.json`: recent updates list.
- `content/*.json`: markdown page bodies loaded only when a detail panel needs them.

The data layer is responsible for normalization, duplicate handling, search fields, project grouping, and sensitive-pattern warnings.

### Frontend Product

`public/index.html` is the main product UI. It consumes only `public/data/*.json` and local assets in `public/assets/`.

P1 features included:

- Full-text search across title, tags, summary, project, community, and body text.
- Project view with project document counts and recent project material.
- Topic view with related content.
- Recent update view.
- Interactive graph view.
- Detail panel with markdown rendering.
- Lazy-loaded page bodies so mobile and private-network access do not pay the full markdown cost upfront.
- Responsive layout for desktop and mobile-sized screens.

## Build Flow

Run from the repository root with a private source path:

```powershell
python tools/build-wiki-product.py --wiki-dir D:\path\to\private\wiki
python tools/validate-wiki-product.py
```

Then serve the repository root:

```powershell
python -m http.server 8790 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8790/public/index.html
```

## Governance Rules

- Data issues should be fixed in the data layer, not hidden in frontend rendering logic.
- Frontend code should not parse or traverse private source directories directly.
- Generated data must preserve stable IDs and expose aliases when data has been normalized.
- Sensitive-pattern warnings must be reviewed before any deployment outside a trusted private network.
- Public commits must never include private source files, generated `public/data/`, runtime logs, raw exports, or screenshots containing private state.
- Product iterations should keep source, generated data, and frontend behavior separate: curate the private source, rebuild ignored `public/data/`, then improve `public/index.html`.

## Next Iteration Hooks

- Add schema validation against `schemas/wiki-product-*.schema.json` once a JSON schema validator is introduced.
- Add private mobile access through a local server, Tailscale, or Cloudflare Access before exposing any full-text data publicly.
