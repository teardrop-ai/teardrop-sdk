"""Contract checks for the SDK surface against the checked-in API specs."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import teardrop.models as models
import teardrop.streaming as streaming

REPO_ROOT = Path(__file__).parents[1]
OPENAPI_PATH = REPO_ROOT / "spec" / "openapi.json"
EVENTS_SCHEMA_PATH = REPO_ROOT / "spec" / "events.schema.json"

EXCLUDED_EXACT_PATHS = {
    "/health",
    "/message:send",
    "/mcp/v1",
    "/token",
}
AGENT_CARD_PATH = "/.well-known/agent-card.json"
HTTP_METHODS = {"get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "delete": "DELETE"}


def _is_excluded_path(path: str) -> bool:
    return path in EXCLUDED_EXACT_PATHS or (
        path.startswith("/.well-known/") and path != AGENT_CARD_PATH
    )


def _normalize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _formatted_value_name(value: ast.FormattedValue) -> str:
    expression = value.value
    if isinstance(expression, ast.Call) and expression.args:
        expression = expression.args[0]
    if isinstance(expression, ast.Name):
        return expression.id
    return "segment"


def _path_from_f_string(value: ast.JoinedStr) -> str:
    parts: list[str] = []
    base_skipped = False
    for item in value.values:
        if isinstance(item, ast.FormattedValue):
            if not base_skipped:
                base_skipped = True
                continue
            parts.append("{" + _formatted_value_name(item) + "}")
        elif base_skipped:
            parts.append(item.value)
    return "".join(parts)


def _sdk_operations() -> set[tuple[str, str]]:
    operations: set[tuple[str, str]] = set()
    client_root = REPO_ROOT / "src" / "teardrop" / "client"
    for source_path in client_root.glob("*.py"):
        tree = ast.parse(source_path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue

            method = node.func.attr
            if method == "stream":
                if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
                    continue
                http_method = node.args[0].value
                url_expression = node.args[1]
            elif method in HTTP_METHODS and node.args:
                http_method = HTTP_METHODS[method]
                url_expression = node.args[0]
            else:
                continue

            if not isinstance(http_method, str):
                continue
            if isinstance(url_expression, ast.JoinedStr):
                path = _path_from_f_string(url_expression)
            elif isinstance(url_expression, ast.Constant) and isinstance(url_expression.value, str):
                path = url_expression.value
            else:
                continue
            if path.startswith("/"):
                operations.add((_normalize_path(path), http_method.upper()))
    return operations


def _openapi_operations(spec: dict[str, Any]) -> set[tuple[str, str]]:
    operations: set[tuple[str, str]] = set()
    for path, path_item in spec["paths"].items():
        if _is_excluded_path(path):
            continue
        for method in path_item:
            if method in HTTP_METHODS:
                operations.add((_normalize_path(path), HTTP_METHODS[method]))
    return operations


def _schema_refs(schema: Any) -> set[str]:
    if isinstance(schema, dict):
        refs = set()
        ref = schema.get("$ref")
        if isinstance(ref, str):
            refs.add(ref.rsplit("/", 1)[-1])
        for value in schema.values():
            refs.update(_schema_refs(value))
        return refs
    if isinstance(schema, list):
        refs = set()
        for value in schema:
            refs.update(_schema_refs(value))
        return refs
    return set()


def test_sdk_operations_match_openapi() -> None:
    spec = json.loads(OPENAPI_PATH.read_text())
    assert _sdk_operations() == _openapi_operations(spec)


def test_server_only_openapi_paths_are_explicitly_excluded() -> None:
    spec = json.loads(OPENAPI_PATH.read_text())
    excluded = {path for path in spec["paths"] if _is_excluded_path(path)}
    assert EXCLUDED_EXACT_PATHS <= excluded
    assert AGENT_CARD_PATH not in excluded
    assert all(path.startswith("/.well-known/") for path in excluded - EXCLUDED_EXACT_PATHS)


def test_response_models_cover_openapi_required_fields() -> None:
    spec = json.loads(OPENAPI_PATH.read_text())
    response_schema_names: set[str] = set()
    for path, path_item in spec["paths"].items():
        if _is_excluded_path(path):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            for response in operation.get("responses", {}).values():
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                response_schema_names.update(_schema_refs(schema))

    component_schemas = spec["components"]["schemas"]
    pending_schema_names = set(response_schema_names)
    response_schema_names = set()
    while pending_schema_names:
        name = pending_schema_names.pop()
        if name in response_schema_names:
            continue
        response_schema_names.add(name)
        pending_schema_names.update(_schema_refs(component_schemas.get(name, {})))

    ignored_schema_names = {"HTTPValidationError", "ValidationError"}
    missing_models = sorted(
        name for name in response_schema_names - ignored_schema_names if not hasattr(models, name)
    )
    assert not missing_models

    missing_fields: dict[str, list[str]] = {}
    non_required_fields: dict[str, list[str]] = {}
    for name in response_schema_names - ignored_schema_names:
        model = getattr(models, name)
        model_fields = set(model.model_fields)
        required_fields = set(spec["components"]["schemas"][name].get("required", []))
        missing = sorted(required_fields - model_fields)
        if missing:
            missing_fields[name] = missing
        not_required = sorted(
            field_name
            for field_name in required_fields & model_fields
            if not model.model_fields[field_name].is_required()
        )
        if not_required:
            non_required_fields[name] = not_required
    assert not missing_fields
    assert not non_required_fields


def test_event_schema_names_have_streaming_constants() -> None:
    schema = json.loads(EVENTS_SCHEMA_PATH.read_text())
    constant_values = {
        value
        for name, value in vars(streaming).items()
        if name.startswith("EVENT_") and isinstance(value, str)
    }
    event_names = set(schema["events"])
    assert event_names - {"Custom"} <= constant_values
    assert "Custom" in event_names
