from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "wiki"
PUBLIC_DIR = ROOT / "public"
DATA_DIR = PUBLIC_DIR / "data"
ASSET_DIR = PUBLIC_DIR / "assets"
CONTENT_DIR = DATA_DIR / "content"

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*", re.S)
HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.M)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
SENSITIVE_PATTERNS = {
    "api_key": re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    "token": re.compile(r"(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*[A-Za-z0-9_\-.]{16,}"),
    "secret": re.compile(r"(?i)(secret|password|passwd)\s*[:=]\s*\S{8,}"),
    "openid": re.compile(r"(?i)(openid|unionid)\s*[:=]\s*[A-Za-z0-9_\-]{8,}"),
}

TYPE_BY_ROOT = {
    "entities": "entity",
    "topics": "topic",
    "sources": "source",
    "comparisons": "comparison",
    "synthesis": "synthesis",
    "queries": "query",
    "ops": "ops",
}


def configure_paths(wiki_dir: Path, public_dir: Path) -> None:
    global WIKI_DIR, PUBLIC_DIR, DATA_DIR, ASSET_DIR, CONTENT_DIR
    WIKI_DIR = wiki_dir.resolve()
    PUBLIC_DIR = public_dir.resolve()
    DATA_DIR = PUBLIC_DIR / "data"
    ASSET_DIR = PUBLIC_DIR / "assets"
    CONTENT_DIR = DATA_DIR / "content"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def content_path_for_id(page_id: str) -> str:
    digest = hashlib.sha1(page_id.encode("utf-8")).hexdigest()
    return f"data/content/{digest}.json"


def parse_frontmatter(markdown: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(markdown or "")
    if not match:
        return {}
    values: dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            values[key] = [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
        else:
            values[key] = value.strip("\"'")
    return values


def strip_frontmatter(markdown: str) -> str:
    return FRONTMATTER_RE.sub("", markdown or "").strip()


def strip_markdown(markdown: str) -> str:
    text = strip_frontmatter(markdown)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`|~\-\[\]{}()]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def first_heading(markdown: str, fallback: str) -> str:
    for level, text in HEADING_RE.findall(markdown or ""):
        if level == "#":
            return text.strip()
    return fallback


def first_summary(markdown: str, plain_text: str) -> str:
    for line in strip_frontmatter(markdown).splitlines():
        line = line.strip()
        if line.startswith(">"):
            return line.lstrip("> ").strip()[:240]
    return plain_text[:240]


def headings(markdown: str) -> list[str]:
    return [text.strip() for level, text in HEADING_RE.findall(strip_frontmatter(markdown)) if len(level) in (2, 3)]


def wiki_links(markdown: str) -> list[str]:
    links = []
    for match in WIKILINK_RE.findall(markdown or ""):
        target = match.split("|", 1)[0].strip()
        if target and target not in links:
            links.append(target)
    return links


def detect_sensitive(text: str) -> list[str]:
    hits = []
    for name, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(text or ""):
            hits.append(name)
    return hits


def rel_id(path: Path) -> str:
    return path.relative_to(WIKI_DIR).with_suffix("").as_posix()


def normalized_rel_from_any_path(value: str) -> str:
    normalized = str(value or "").replace("\\", "/")
    marker = "/wiki/"
    if marker in normalized.lower():
        index = normalized.lower().rindex(marker)
        normalized = normalized[index + len(marker):]
    return normalized


def type_and_project(path: Path) -> tuple[str, str]:
    rel = path.relative_to(WIKI_DIR)
    parts = rel.parts
    if not parts:
        return "page", ""
    if parts[0] == "projects" and len(parts) >= 2:
        if len(parts) == 2 and parts[1].lower() == "readme.md":
            return "page", ""
        if len(parts) == 3 and parts[2].lower() == "readme.md":
            return "project", parts[1]
        if len(parts) < 3:
            return "page", ""
        return "project-doc", parts[1]
    return TYPE_BY_ROOT.get(parts[0], "page"), ""


def read_pages() -> list[dict[str, Any]]:
    pages = []
    for path in sorted(WIKI_DIR.rglob("*.md")):
        rel = path.relative_to(WIKI_DIR).as_posix()
        if rel.startswith("public/"):
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        frontmatter = parse_frontmatter(content)
        plain = strip_markdown(content)
        page_type, project = type_and_project(path)
        tags = frontmatter.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        title = first_heading(content, path.stem)
        page = {
            "id": rel_id(path),
            "label": title,
            "title": title,
            "type": page_type,
            "community": project or frontmatter.get("community", ""),
            "project": project,
            "source_path": rel,
            "aliases": [],
            "tags": tags,
            "created": str(frontmatter.get("created", "")),
            "updated": str(frontmatter.get("updated", "")),
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "sources": frontmatter.get("sources", []),
            "summary": first_summary(content, plain),
            "headings": headings(content),
            "wiki_links": wiki_links(content),
            "content": strip_frontmatter(content),
            "text": plain,
            "word_count": len(plain),
            "degree": 0,
            "sensitive_hits": detect_sensitive(content),
        }
        page["search_text"] = " ".join(
            str(value)
            for value in [
                page["title"],
                page["label"],
                page["type"],
                page["community"],
                page["project"],
                " ".join(page["tags"]),
                page["summary"],
                page["text"],
            ]
        ).lower()
        pages.append(page)
    return pages


def build_alias_indexes(pages: list[dict[str, Any]]) -> dict[str, str]:
    candidates: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        aliases = {
            page["id"],
            page["title"],
            page["label"],
            Path(page["source_path"]).stem,
            Path(page["source_path"]).with_suffix("").as_posix(),
        }
        for alias in aliases:
            key = str(alias).strip().lower()
            if key:
                candidates[key].append(page["id"])
    return {key: ids[0] for key, ids in candidates.items() if len(ids) == 1}


def edge_key(edge: dict[str, Any]) -> tuple[str, str, str]:
    return str(edge.get("from", "")), str(edge.get("to", "")), str(edge.get("type", ""))


def add_edge(edges: list[dict[str, Any]], seen: set[tuple[str, str, str]], source: str, target: str, edge_type: str, weight: float = 1) -> None:
    if not source or not target or source == target:
        return
    edge = {"id": f"e{len(edges) + 1}", "from": source, "to": target, "type": edge_type, "weight": weight}
    key = edge_key(edge)
    if key in seen:
        return
    seen.add(key)
    edges.append(edge)


def seed_edges_from_graph(graph_path: Path, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not graph_path.exists():
        return []
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    rel_to_id = {page["source_path"]: page["id"] for page in pages}
    old_id_to_new_id = {}
    for node in graph.get("nodes", []):
        rel = normalized_rel_from_any_path(node.get("source_path", ""))
        if rel in rel_to_id:
            old_id_to_new_id[node.get("id")] = rel_to_id[rel]
    seeded = []
    seen: set[tuple[str, str, str]] = set()
    for edge in graph.get("edges", []):
        source = old_id_to_new_id.get(edge.get("from"))
        target = old_id_to_new_id.get(edge.get("to"))
        add_edge(seeded, seen, source, target, edge.get("type", "GRAPH"), float(edge.get("weight", 1) or 1))
    return seeded


def build_edges(pages: list[dict[str, Any]], graph_path: Path) -> list[dict[str, Any]]:
    edges = seed_edges_from_graph(graph_path, pages)
    seen = {edge_key(edge) for edge in edges}
    alias_index = build_alias_indexes(pages)
    project_roots = {page["project"]: page["id"] for page in pages if page["type"] == "project" and page["project"]}
    for page in pages:
        if page["project"] and page["type"] != "project":
            add_edge(edges, seen, page["id"], project_roots.get(page["project"], ""), "PROJECT", 0.8)
        for link in page["wiki_links"]:
            target = alias_index.get(link.lower())
            add_edge(edges, seen, page["id"], target, "WIKILINK", 1)
        sources = page.get("sources") or []
        if isinstance(sources, str):
            sources = [sources]
        for source in sources:
            target = alias_index.get(str(source).lower())
            add_edge(edges, seen, page["id"], target, "SOURCE", 0.8)
    return edges


def sortable_date(item: dict[str, Any]) -> str:
    return str(item.get("updated") or item.get("created") or item.get("modified") or "")


def search_item(page: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "id",
        "label",
        "title",
        "type",
        "community",
        "project",
        "source_path",
        "aliases",
        "tags",
        "created",
        "updated",
        "modified",
        "sources",
        "summary",
        "headings",
        "wiki_links",
        "word_count",
        "degree",
        "sensitive_hits",
        "search_text",
        "content_path",
    ]
    return {key: page[key] for key in keys}


def content_item(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": page["id"],
        "title": page["title"],
        "type": page["type"],
        "project": page["project"],
        "source_path": page["source_path"],
        "updated": page["updated"],
        "created": page["created"],
        "modified": page["modified"],
        "content": page["content"],
    }


def build_indexes(pages: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree: Counter[str] = Counter()
    for edge in edges:
        degree[str(edge.get("from", ""))] += 1
        degree[str(edge.get("to", ""))] += 1
    for page in pages:
        page["degree"] = degree[page["id"]]
        page["content_path"] = content_path_for_id(page["id"])
    pages.sort(key=lambda item: (item["type"], item["title"], item["source_path"]))

    graph_nodes = [
        {
            key: page[key]
            for key in [
                "id",
                "label",
                "title",
                "type",
                "community",
                "project",
                "source_path",
                "aliases",
                "tags",
                "summary",
                "updated",
                "degree",
            ]
        }
        for page in pages
    ]

    project_docs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in pages:
        if page["project"]:
            project_docs[page["project"]].append(page)
    project_items = []
    for page in pages:
        if page["type"] != "project":
            continue
        docs = project_docs.get(page["project"], [])
        project_items.append(
            {
                "id": page["id"],
                "project_id": page["project"],
                "title": page["title"],
                "label": page["label"],
                "summary": page["summary"],
                "source_path": page["source_path"],
                "aliases": page["aliases"],
                "doc_count": len(docs),
                "session_count": sum(1 for doc in docs if "/sessions/" in doc["source_path"] or "/session-ledger/" in doc["source_path"]),
                "latest": max((sortable_date(doc) for doc in docs), default=sortable_date(page)),
                "top_docs": [
                    {
                        "id": doc["id"],
                        "title": doc["title"],
                        "type": doc["type"],
                        "updated": doc["updated"],
                        "created": doc["created"],
                        "modified": doc["modified"],
                    }
                    for doc in sorted(docs, key=sortable_date, reverse=True)[:8]
                ],
            }
        )
    project_items.sort(key=lambda item: item["title"])

    topic_items = []
    for page in pages:
        if page["type"] != "topic":
            continue
        related = [doc for doc in pages if page["title"] in doc["wiki_links"] or doc["community"] == page["title"]]
        topic_items.append(
            {
                "id": page["id"],
                "title": page["title"],
                "summary": page["summary"],
                "tags": page["tags"],
                "source_path": page["source_path"],
                "related_count": len(related),
                "top_related": [
                    {
                        "id": doc["id"],
                        "title": doc["title"],
                        "type": doc["type"],
                        "updated": doc["updated"],
                        "created": doc["created"],
                        "modified": doc["modified"],
                    }
                    for doc in sorted(related, key=lambda doc: (doc["degree"], sortable_date(doc)), reverse=True)[:8]
                ],
            }
        )
    topic_items.sort(key=lambda item: item["title"])

    recent_items = sorted(pages, key=sortable_date, reverse=True)[:100]
    type_counts = Counter(page["type"] for page in pages)
    project_counts = Counter(page["project"] for page in pages if page["project"])
    tag_counts = Counter(tag for page in pages for tag in page["tags"])
    sensitive_items = [page for page in pages if page["sensitive_hits"]]
    build_date = datetime.now().isoformat(timespec="seconds")
    meta = {
        "build_date": build_date,
        "wiki_title": "个人知识库",
        "total_pages": len(pages),
        "total_nodes": len(graph_nodes),
        "total_edges": len(edges),
        "type_counts": dict(sorted(type_counts.items())),
        "project_counts": dict(sorted(project_counts.items())),
        "tag_counts": dict(tag_counts.most_common(30)),
        "project_count": len(project_items),
        "topic_count": len(topic_items),
        "recent_count": len(recent_items),
        "sensitive_hit_count": len(sensitive_items),
        "sensitive_hit_ids": [page["id"] for page in sensitive_items[:30]],
        "data_files": [
            "meta.json",
            "graph-data.json",
            "search-index.json",
            "project-index.json",
            "topic-index.json",
            "recent-index.json",
            "content/*.json",
        ],
        "content_count": len(pages),
    }
    return {
        "meta": meta,
        "graph": {
            "meta": {
                "build_date": build_date,
                "wiki_title": meta["wiki_title"],
                "total_nodes": len(graph_nodes),
                "total_edges": len(edges),
                "type_counts": meta["type_counts"],
            },
            "nodes": graph_nodes,
            "edges": edges,
        },
        "search": {"meta": meta, "items": [search_item(page) for page in pages]},
        "content": [{"path": page["content_path"], "item": content_item(page)} for page in pages],
        "projects": {"meta": {"build_date": build_date, "project_count": len(project_items)}, "projects": project_items},
        "topics": {
            "meta": {"build_date": build_date, "topic_count": len(topic_items)},
            "topics": topic_items,
            "top_tags": [{"tag": tag, "count": count} for tag, count in tag_counts.most_common(40)],
        },
        "recent": {
            "meta": {"build_date": build_date, "recent_count": len(recent_items)},
            "items": [
                {
                    "id": page["id"],
                    "title": page["title"],
                    "type": page["type"],
                    "project": page["project"],
                    "summary": page["summary"],
                    "updated": page["updated"],
                    "created": page["created"],
                    "modified": page["modified"],
                    "source_path": page["source_path"],
                }
                for page in recent_items
            ],
        },
    }


def copy_assets() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["d3.min.js", "marked.min.js", "purify.min.js"]:
        for source in [WIKI_DIR / name, ROOT / "public" / "assets" / name]:
            if source.exists():
                shutil.copy2(source, ASSET_DIR / name)
                break


def build(args: argparse.Namespace) -> None:
    if not WIKI_DIR.exists():
        raise SystemExit(f"Wiki source directory not found: {WIKI_DIR}")
    pages = read_pages()
    if not pages:
        raise SystemExit(f"No markdown pages found under: {WIKI_DIR}")
    edges = build_edges(pages, args.graph)
    indexes = build_indexes(pages, edges)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONTENT_DIR.exists():
        shutil.rmtree(CONTENT_DIR)
    write_json(DATA_DIR / "meta.json", indexes["meta"])
    write_json(DATA_DIR / "graph-data.json", indexes["graph"])
    write_json(DATA_DIR / "search-index.json", indexes["search"])
    write_json(DATA_DIR / "project-index.json", indexes["projects"])
    write_json(DATA_DIR / "topic-index.json", indexes["topics"])
    write_json(DATA_DIR / "recent-index.json", indexes["recent"])
    for content in indexes["content"]:
        write_json(PUBLIC_DIR / content["path"], content["item"])
    copy_assets()
    print(f"Built public data: {indexes['meta']['total_pages']} pages, {indexes['meta']['total_edges']} edges")
    if indexes["meta"]["sensitive_hit_count"]:
        print(f"Sensitive-pattern warnings: {indexes['meta']['sensitive_hit_count']} items")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build separated data artifacts for the llm-wiki product frontend.")
    parser.add_argument("--wiki-dir", type=Path, default=ROOT / "wiki", help="Private Markdown wiki source directory. This directory is ignored by Git.")
    parser.add_argument("--public-dir", type=Path, default=ROOT / "public", help="Frontend output directory.")
    parser.add_argument("--graph", type=Path, default=None, help="Optional existing graph-data.json to seed graph edges.")
    args = parser.parse_args()
    configure_paths(args.wiki_dir, args.public_dir)
    if args.graph is None:
        args.graph = WIKI_DIR / "graph-data.json"
    build(args)


if __name__ == "__main__":
    main()
