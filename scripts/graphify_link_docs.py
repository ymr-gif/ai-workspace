#!/usr/bin/env python3
"""Bridge graphify's doc layer to its code layer.

graphify builds two disjoint islands: AST nodes (ids derived from source
symbols) and semantic doc nodes (ids derived from the prose that describes
them). Nothing links them, so `graphify path "<a design decision>" "<the
function that implements it>"` never resolves even when both nodes exist.

This linker closes the gap deterministically — no LLM, no tokens. It matches
identifier-shaped tokens in a doc node's label/rationale against code node
labels, and only keeps a match when the doc file backticks the symbol, which
is what separates "the docs name this function" from "an English word that
happens to be a symbol name".

Run after every rebuild:

    python3 scripts/graphify_link_docs.py            # apply
    python3 scripts/graphify_link_docs.py --dry-run  # preview only

Edges are tagged `linked_by: doc_code_linker` and re-applying is idempotent:
a re-run strips the previous generation before relinking, so it is safe to
chain straight after `graphify update .` or a full re-enrich.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

GRAPH_DEFAULT = Path("graphify-out/graph.json")
MARKER = "doc_code_linker"

# Node file_types that make up the semantic (prose) half of the graph.
DOC_TYPES = {"document", "paper", "image", "rationale", "concept"}

# Minimum token length. Shorter identifiers collide with prose constantly.
MIN_TOKEN_LEN = 6

# Identifiers that are also ordinary English or too generic to disambiguate,
# even when they pass the shape test.
STOPWORDS = {
    "startup", "shutdown", "version", "versions", "models", "client", "clients",
    "health", "hardware", "metrics", "retrieve", "snapshot", "snapshots",
    "throwaway", "dependencies", "settings", "storage", "records", "message",
    "messages", "summary", "context", "content", "process", "results",
}

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.(?:py|jsx?|tsx?|sh|ya?ml))?")
TRAILING_CALL_RE = re.compile(r"\(\)$")


def identifier_shaped(token: str) -> bool:
    """True when the token looks like code rather than a word of prose."""
    if re.search(r"\.(py|jsx?|tsx?|sh|ya?ml)$", token):
        return True
    if "_" in token:
        return True
    if re.search(r"[a-z][A-Z]", token):           # camelCase
        return True
    if re.match(r"^[A-Z][a-z]+[A-Z]", token):     # PascalCase
        return True
    return False


def build_code_index(code_nodes: list[dict]) -> tuple[dict[str, str], set[str]]:
    """label -> node id, plus the set of labels that are ambiguous.

    A label owned by more than one node (``main``, ``__init__.py``, every
    ``upgrade()`` in alembic) cannot be resolved from a doc mention alone, so
    it is dropped rather than guessed.
    """
    by_label: dict[str, list[str]] = collections.defaultdict(list)
    for node in code_nodes:
        label = TRAILING_CALL_RE.sub("", (node.get("label") or "").strip())
        if label:
            by_label[label].append(node["id"])
    ambiguous = {label for label, ids in by_label.items() if len(ids) > 1}
    index = {label: ids[0] for label, ids in by_label.items() if label not in ambiguous}
    return index, ambiguous


def doc_mentions(node: dict, index: dict[str, str], source_cache: dict[str, str],
                 repo_root: Path) -> list[tuple[str, str]]:
    """Symbols this doc node names AND its source file backticks."""
    haystack = " ".join(str(node.get(key) or "") for key in ("label", "rationale"))
    rel = node.get("source_file") or ""
    if rel not in source_cache:
        path = repo_root / rel
        source_cache[rel] = (
            path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        )
    body = source_cache[rel]

    found = []
    for token in sorted(set(TOKEN_RE.findall(haystack))):
        if len(token) < MIN_TOKEN_LEN or token in STOPWORDS:
            continue
        if not identifier_shaped(token) or token not in index:
            continue
        # The doc must present it as code, not prose.
        if f"`{token}`" in body or f"`{token}()`" in body or f"`{token}(" in body:
            found.append((token, index[token]))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=GRAPH_DEFAULT,
                        help="path to graph.json (default: graphify-out/graph.json)")
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="repo root that source_file paths are relative to")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the edges that would be added, write nothing")
    parser.add_argument("--relation", default="references",
                        help="edge relation to emit (default: references)")
    parser.add_argument("--score", type=float, default=0.95,
                        help="confidence_score for emitted edges (default: 0.95 — "
                             "named cross-file reference)")
    args = parser.parse_args()

    if not args.graph.is_file():
        print(f"error: {args.graph} not found — build the graph first", file=sys.stderr)
        return 1

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    nodes = graph["nodes"]
    links = graph["links"]

    docs = [n for n in nodes if n.get("file_type") in DOC_TYPES]
    code = [n for n in nodes if n.get("file_type") not in DOC_TYPES]
    index, ambiguous = build_code_index(code)

    # Drop the previous generation so re-runs stay idempotent.
    stale = sum(1 for link in links if link.get("linked_by") == MARKER)
    kept = [link for link in links if link.get("linked_by") != MARKER]
    existing = {(link["source"], link["target"]) for link in kept}

    source_cache: dict[str, str] = {}
    new_links = []
    for node in docs:
        for token, target in doc_mentions(node, index, source_cache, args.root):
            pair = (node["id"], target)
            if pair in existing or target == node["id"]:
                continue
            existing.add(pair)
            new_links.append({
                "relation": args.relation,
                "confidence": "INFERRED",
                "confidence_score": args.score,
                "source_file": node.get("source_file"),
                "source_location": node.get("source_location"),
                "weight": 1.0,
                "source": node["id"],
                "target": target,
                "linked_by": MARKER,
                "matched_symbol": token,
            })

    print(f"doc nodes: {len(docs)}  code nodes: {len(code)}")
    print(f"resolvable code labels: {len(index)}  (dropped {len(ambiguous)} ambiguous)")
    if stale:
        print(f"replacing {stale} edge(s) from a previous linker run")
    print(f"bridge edges: {len(new_links)}")
    for link in new_links:
        print(f"  {link['source']} --{args.relation}--> {link['target']}"
              f"  (via `{link['matched_symbol']}`)")

    if args.dry_run:
        print("\ndry run — graph.json untouched")
        return 0

    graph["links"] = kept + new_links
    args.graph.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {args.graph} ({len(graph['links'])} edges total)")
    print("regenerate views: graphify export html && graphify export wiki")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
