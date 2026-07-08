# llm-wiki Product

Code-only public shell for a personal Markdown knowledge-base product.

This repository contains the reusable frontend, data builder, schemas, and validation scripts. It intentionally does not include private knowledge content, generated graph data, project mirrors, runtime logs, or secrets.

## What Is Included

- `public/index.html`: interactive wiki workbench UI.
- `public/assets/`: local browser assets used by the frontend.
- `tools/build-wiki-product.py`: builds frontend data from a private Markdown wiki.
- `tools/validate-wiki-product.py`: validates generated data after a private local build.
- `tools/check-public-scope.py`: prevents private data from being published.
- `schemas/`: JSON data contracts for generated artifacts.
- `docs/architecture.md`: source/data/frontend separation notes.

## What Is Not Included

- `wiki/` Markdown source content.
- `public/data/` generated indexes and page bodies.
- Raw project mirrors, chat exports, runtime reports, or logs.
- Credentials, tokens, cookies, API responses, or private screenshots.

## Local Use

Build data from a private wiki directory:

```powershell
python tools/build-wiki-product.py --wiki-dir D:\path\to\private\wiki
python tools/validate-wiki-product.py
```

Serve the product locally:

```powershell
python -m http.server 8790 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8790/public/index.html
```

## Public Release Guard

Before publishing, run:

```powershell
python tools/check-public-scope.py
```

The guard fails if private source or generated data paths such as `wiki/`, `public/data/`, `raw/`, or `runtime/` are present in the repository tree.

## Data Flow

```text
private wiki/ Markdown
  -> tools/build-wiki-product.py
  -> ignored public/data/*.json
  -> public/index.html
```

The public repository is the product architecture. Your private knowledge base remains outside GitHub.
