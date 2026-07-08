from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
DATA_DIR = PUBLIC_DIR / "data"
ASSET_DIR = PUBLIC_DIR / "assets"

DATA_FILES = {
    "meta": DATA_DIR / "meta.json",
    "graph": DATA_DIR / "graph-data.json",
    "search": DATA_DIR / "search-index.json",
    "projects": DATA_DIR / "project-index.json",
    "topics": DATA_DIR / "topic-index.json",
    "recent": DATA_DIR / "recent-index.json",
}
ASSET_FILES = ["d3.min.js", "marked.min.js", "purify.min.js"]
CONTENT_DIR = DATA_DIR / "content"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def warn(warnings: list[str], message: str) -> None:
    warnings.append(message)


def validate() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for name, path in DATA_FILES.items():
        if not path.exists():
            fail(errors, f"missing data file: {path}")
    for name in ASSET_FILES:
        if not (ASSET_DIR / name).exists():
            fail(errors, f"missing frontend asset: {ASSET_DIR / name}")
    if errors:
        return report(errors, warnings, None)

    data = {name: load_json(path) for name, path in DATA_FILES.items()}
    meta = data["meta"]
    graph = data["graph"]
    search = data["search"]
    projects = data["projects"]
    topics = data["topics"]
    recent = data["recent"]

    search_items = search.get("items", [])
    graph_nodes = graph.get("nodes", [])
    graph_edges = graph.get("edges", [])
    node_ids = {str(node.get("id", "")) for node in graph_nodes}
    item_ids = [str(item.get("id", "")) for item in search_items]

    if len(search_items) != meta.get("total_pages"):
        fail(errors, "meta.total_pages does not match search-index item count")
    if len(graph_nodes) != meta.get("total_nodes"):
        fail(errors, "meta.total_nodes does not match graph node count")
    if len(graph_edges) != meta.get("total_edges"):
        fail(errors, "meta.total_edges does not match graph edge count")
    if len(item_ids) != len(set(item_ids)):
        fail(errors, "search-index contains duplicate item ids")
    if node_ids != set(item_ids):
        fail(errors, "graph nodes and search-index items do not expose the same ids")
    missing_content = []
    embedded_content = []
    for item in search_items:
        if "content" in item or "text" in item:
            embedded_content.append(item.get("id"))
        content_path = str(item.get("content_path", ""))
        if not content_path.startswith("data/content/"):
            missing_content.append(item.get("id"))
            continue
        if not (PUBLIC_DIR / content_path).exists():
            missing_content.append(item.get("id"))
    if embedded_content:
        fail(errors, f"search-index embeds full page bodies for {len(embedded_content)} items")
    if missing_content:
        fail(errors, f"missing page content files for {len(missing_content)} items")

    missing_edges = [
        edge
        for edge in graph_edges
        if str(edge.get("from", "")) not in node_ids or str(edge.get("to", "")) not in node_ids
    ]
    if missing_edges:
        fail(errors, f"graph contains {len(missing_edges)} edges with missing node references")

    project_items = projects.get("projects", [])
    topic_items = topics.get("topics", [])
    recent_items = recent.get("items", [])
    if len(project_items) != meta.get("project_count"):
        fail(errors, "meta.project_count does not match project-index")
    if len(topic_items) != meta.get("topic_count"):
        fail(errors, "meta.topic_count does not match topic-index")
    if len(recent_items) != meta.get("recent_count"):
        fail(errors, "meta.recent_count does not match recent-index")

    missing_recent = [item.get("id") for item in recent_items if str(item.get("id", "")) not in node_ids]
    if missing_recent:
        fail(errors, f"recent-index references missing ids: {missing_recent[:5]}")

    html_path = PUBLIC_DIR / "index.html"
    if not html_path.exists():
        fail(errors, f"missing frontend entry: {html_path}")
    else:
        html = html_path.read_text(encoding="utf-8")
        for path in ["data/meta.json", "data/graph-data.json", "data/search-index.json"]:
            if path not in html:
                fail(errors, f"frontend does not load required data artifact: {path}")
        if "content_path" not in html:
            fail(errors, "frontend does not lazy-load page content")
        if "wiki/" in html or "../wiki" in html:
            fail(errors, "frontend appears to reference the source wiki directory")

    if meta.get("sensitive_hit_count"):
        warn(warnings, f"sensitive-pattern warnings: {meta.get('sensitive_hit_count')}")

    stats = {
        "pages": len(search_items),
        "nodes": len(graph_nodes),
        "edges": len(graph_edges),
        "projects": len(project_items),
        "topics": len(topic_items),
        "recent": len(recent_items),
    }
    return report(errors, warnings, stats)


def report(errors: list[str], warnings: list[str], stats: dict[str, int] | None) -> int:
    if stats:
        print(
            "Wiki product data OK: "
            f"{stats['pages']} pages, {stats['edges']} edges, "
            f"{stats['projects']} projects, {stats['topics']} topics"
        )
    for message in warnings:
        print(f"WARNING: {message}")
    for message in errors:
        print(f"ERROR: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(validate())
