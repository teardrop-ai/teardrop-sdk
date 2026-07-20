#!/usr/bin/env python3
"""Structural diff of spec/openapi.json (and optionally events.schema.json)
against a git base ref (default: origin/main).

Why this exists: spec/openapi.json is large (300+ KB, ~12k lines). Reading it
whole into an agent's context to eyeball a diff is slow and error-prone. This
script computes a small, deterministic, de-noised structural diff instead:

    - added/removed paths+operations (HTTP method + path)
    - added/removed component schemas
    - changed common schemas: added/removed properties, added/removed
      required fields (flags newly-required fields as breaking-for-responses)
    - with --events: added/removed SSE event names in events.schema.json

Only stdlib is used (json, subprocess, argparse, pathlib) so this runs with
any Python interpreter available on PATH -- no project venv needed.

Usage:
    python diff_openapi.py [BASE_REF] [--events] [--max-lines N]

    BASE_REF     git ref to diff against (default: origin/main)
    --events     also diff spec/events.schema.json event names
    --max-lines  cap output lines per section (default: 60)

Limitations: schemas composed via allOf/$ref without inline "properties" will
show no property-level detail here -- fall back to a targeted
`git diff <base_ref> -- spec/openapi.json` scoped with grep around the schema
name for those.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return Path(result.stdout.strip())


def _load_git_json(ref: str, rel_path: str, repo_root: Path) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _load_local_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _operations(spec: dict[str, Any]) -> set[tuple[str, str]]:
    ops: set[tuple[str, str]] = set()
    for path, item in spec.get("paths", {}).items():
        for method in item:
            if method in HTTP_METHODS:
                ops.add((method.upper(), path))
    return ops


def _schema_shape(schema: dict[str, Any]) -> tuple[frozenset[str], frozenset[str]]:
    props = frozenset((schema.get("properties") or {}).keys())
    required = frozenset(schema.get("required") or [])
    return props, required


def diff_openapi(old: dict[str, Any] | None, new: dict[str, Any], max_lines: int) -> str:
    lines: list[str] = ["## Operations"]

    old_ops = _operations(old) if old else set()
    new_ops = _operations(new)
    added_ops = sorted(new_ops - old_ops)
    removed_ops = sorted(old_ops - new_ops)

    if added_ops:
        lines.append("Added:")
        lines += [f"  + {m} {p}" for m, p in added_ops[:max_lines]]
    if removed_ops:
        lines.append("Removed:")
        lines += [f"  - {m} {p}" for m, p in removed_ops[:max_lines]]
    if not added_ops and not removed_ops:
        lines.append("(no path/method changes)")

    old_schemas = (old or {}).get("components", {}).get("schemas", {})
    new_schemas = new.get("components", {}).get("schemas", {})
    old_names = set(old_schemas)
    new_names = set(new_schemas)

    added_schemas = sorted(new_names - old_names)
    removed_schemas = sorted(old_names - new_names)
    common_schemas = sorted(old_names & new_names)

    lines.append("")
    lines.append("## Component Schemas")
    if added_schemas:
        lines.append("Added schemas: " + ", ".join(added_schemas[:max_lines]))
    if removed_schemas:
        lines.append("Removed schemas: " + ", ".join(removed_schemas[:max_lines]))

    changed = 0
    for name in common_schemas:
        old_props, old_req = _schema_shape(old_schemas[name])
        new_props, new_req = _schema_shape(new_schemas[name])
        prop_added = sorted(new_props - old_props)
        prop_removed = sorted(old_props - new_props)
        req_added = sorted(new_req - old_req)
        req_removed = sorted(old_req - new_req)
        if not (prop_added or prop_removed or req_added or req_removed):
            continue
        changed += 1
        if changed > max_lines:
            lines.append(f"... ({changed - max_lines} more changed schemas truncated)")
            break
        lines.append(f"- {name}:")
        if prop_added:
            lines.append(f"    +props {prop_added}")
        if prop_removed:
            lines.append(f"    -props {prop_removed}")
        if req_added:
            lines.append(
                f"    +required {req_added}  "
                "(BREAKING for existing callers if this is a response schema)"
            )
        if req_removed:
            lines.append(f"    -required {req_removed}")
    if changed == 0:
        lines.append("(no changed common schemas)")

    return "\n".join(lines)


def diff_events(old: dict[str, Any] | None, new: dict[str, Any]) -> str:
    old_events = set((old or {}).get("events", {}))
    new_events = set(new.get("events", {}))
    added = sorted(new_events - old_events)
    removed = sorted(old_events - new_events)

    lines = ["## Events"]
    if added:
        lines.append("Added: " + ", ".join(added))
    if removed:
        lines.append("Removed: " + ", ".join(removed))
    if not added and not removed:
        lines.append("(no event name changes)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_ref", nargs="?", default="origin/main")
    parser.add_argument("--events", action="store_true", help="also diff spec/events.schema.json")
    parser.add_argument("--max-lines", type=int, default=60)
    args = parser.parse_args()

    repo_root = _repo_root()
    new_spec = _load_local_json(repo_root / "spec" / "openapi.json")
    if new_spec is None:
        print("spec/openapi.json not found in working tree", file=sys.stderr)
        return 1

    old_spec = _load_git_json(args.base_ref, "spec/openapi.json", repo_root)
    if old_spec is None:
        print(
            f"(warning) could not read spec/openapi.json at '{args.base_ref}'; "
            "treating everything as added",
            file=sys.stderr,
        )

    old_version = (old_spec or {}).get("info", {}).get("version", "?")
    new_version = new_spec.get("info", {}).get("version", "?")
    print(f"# openapi.json: {old_version} -> {new_version} (base: {args.base_ref})\n")
    print(diff_openapi(old_spec, new_spec, args.max_lines))

    if args.events:
        old_events_spec = _load_git_json(args.base_ref, "spec/events.schema.json", repo_root)
        new_events_spec = _load_local_json(repo_root / "spec" / "events.schema.json")
        if new_events_spec is not None:
            print()
            old_ev_version = (old_events_spec or {}).get("version", "?")
            new_ev_version = new_events_spec.get("version", "?")
            print(f"# events.schema.json: {old_ev_version} -> {new_ev_version}\n")
            print(diff_events(old_events_spec, new_events_spec))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
