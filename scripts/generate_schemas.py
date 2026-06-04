#!/usr/bin/env python3
"""Generate apps/web/schemas/*.ts from packages/schemas/*.py.

packages/schemas/ is the Single Source of Truth for all shared schemas.
This script derives TypeScript / Zod equivalents via Pydantic's model_json_schema()
instead of inspecting type annotations directly — JSON Schema is stable and handles
datetime, UUID, enums, and cross-file references automatically.

Usage:
    uv run python scripts/generate_schemas.py
    make codegen
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path
from typing import Any, get_args

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402

import packages.schemas.evaluations as _eval  # noqa: E402
import packages.schemas.jobs as _jobs  # noqa: E402
import packages.schemas.recommendation as _rec  # noqa: E402
import packages.schemas.sse_events as _sse  # noqa: E402

# ---------------------------------------------------------------------------
# Global model registry: class name → TS file key (matches output filename stem)
# ---------------------------------------------------------------------------

_MODEL_FILE: dict[str, str] = {}


def _register(mod: _types.ModuleType, file_key: str) -> None:
    for name, obj in vars(mod).items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
            and obj.__module__ == mod.__name__
        ):
            _MODEL_FILE[name] = file_key


_register(_rec, "recommendation")
_register(_eval, "evaluations")
_register(_jobs, "jobs")
_register(_sse, "sse-events")


# ---------------------------------------------------------------------------
# JSON Schema → Zod expression string
# ---------------------------------------------------------------------------


def _zod(schema: dict[str, Any], imports: set[str], current_file: str) -> str:  # noqa: ANN401
    # $ref → named schema constant; add cross-file import if needed
    if "$ref" in schema:
        model_name = schema["$ref"].split("/")[-1]
        owner = _MODEL_FILE.get(model_name, current_file)
        if owner != current_file:
            imports.add(f'import {{ {model_name}Schema }} from "./{owner}";')
        return f"{model_name}Schema"

    # const → z.literal (discriminator literal values)
    if "const" in schema:
        v = schema["const"]
        return f'z.literal("{v}")' if isinstance(v, str) else f"z.literal({str(v).lower()})"

    # enum → z.literal (single) or z.enum (multiple)
    if "enum" in schema:
        vals = [f'"{v}"' if isinstance(v, str) else str(v).lower() for v in schema["enum"]]
        return f"z.literal({vals[0]})" if len(vals) == 1 else f"z.enum([{', '.join(vals)}])"

    # anyOf — handles `X | None` and `Optional[X]` patterns
    if "anyOf" in schema:
        null_s: dict[str, Any] = {"type": "null"}
        non_null = [s for s in schema["anyOf"] if s != null_s]
        has_null = null_s in schema["anyOf"]
        if len(non_null) == 1:
            base = _zod(non_null[0], imports, current_file)
            return f"{base}.nullable().optional()" if has_null else base
        branches = ", ".join(_zod(s, imports, current_file) for s in non_null)
        base = f"z.union([{branches}])"
        return f"{base}.nullable().optional()" if has_null else base

    type_ = schema.get("type", "")
    fmt = schema.get("format", "")

    if type_ == "string":
        if fmt == "uuid":
            return "z.string().uuid()"
        if fmt == "date-time":
            return "z.string().datetime()"
        return "z.string()"
    if type_ == "integer":
        return "z.number().int()"
    if type_ == "number":
        return "z.number()"
    if type_ == "boolean":
        return "z.boolean()"
    if type_ == "null":
        return "z.null()"
    if type_ == "array":
        inner = _zod(schema.get("items", {}), imports, current_file)
        return f"z.array({inner})"
    if type_ == "object":
        if "properties" in schema:
            lines = ["z.object({"]
            for k, v in schema["properties"].items():
                lines.append(f"  {k}: {_zod(v, imports, current_file)},")
            lines.append("})")
            return "\n".join(lines)
        add = schema.get("additionalProperties")
        if isinstance(add, dict):
            return f"z.record({_zod(add, imports, current_file)})"
        return "z.record(z.unknown())"

    return "z.unknown()"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_models(mod: _types.ModuleType) -> list[type[BaseModel]]:
    return [
        obj
        for _name, obj in vars(mod).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj is not BaseModel
        and obj.__module__ == mod.__name__
    ]


def _union_members(union_annotation: Any) -> list[type[BaseModel]]:  # noqa: ANN401
    """Extract ordered BaseModel members from Annotated[Union[M1, M2, ...], Field(...)]."""
    annotated_args = get_args(union_annotation)
    if not annotated_args:
        return []
    return [
        a
        for a in get_args(annotated_args[0])
        if isinstance(a, type) and issubclass(a, BaseModel)
    ]


def _make_header(py_module: str, imports: set[str]) -> str:
    lines = ['import { z } from "zod";']
    if imports:
        lines.append("")
        lines.extend(sorted(imports))
    lines += [
        "",
        "// AUTO-GENERATED — do not edit by hand.",
        f"// Single Source of Truth: packages/schemas/{py_module}.py",
        "// Regenerate:  make codegen",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generate one TS file
# ---------------------------------------------------------------------------


def generate_file(
    mod: _types.ModuleType,
    out_path: Path,
    py_module: str,
    file_key: str,
    discriminated_union: tuple[str, Any] | None = None,  # noqa: ANN401
) -> None:
    imports: set[str] = set()
    blocks: list[str] = []

    for cls in _collect_models(mod):
        full_schema = cls.model_json_schema()
        props = full_schema.get("properties", {})
        lines = [f"export const {cls.__name__}Schema = z.object({{"]
        for field_name, field_schema in props.items():
            zod_expr = _zod(field_schema, imports, file_key)
            lines.append(f"  {field_name}: {zod_expr},")
        lines.append("});")
        blocks.append("\n".join(lines))

    if discriminated_union:
        discriminator, union_type = discriminated_union
        members = _union_members(union_type)
        member_list = "\n  ".join(f"{m.__name__}Schema," for m in members)
        blocks.append(
            f'export const SseEventSchema = z.discriminatedUnion("{discriminator}", [\n'
            f"  {member_list}\n"
            f"]);"
        )
        blocks.append("export type SseEvent = z.infer<typeof SseEventSchema>;")

    content = _make_header(py_module, imports) + "\n\n".join(blocks) + "\n"
    out_path.write_text(content)
    print(f"Generated {out_path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_OUT = ROOT / "apps/web/schemas"


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    generate_file(_rec, _OUT / "recommendation.ts", "recommendation", "recommendation")
    generate_file(_eval, _OUT / "evaluations.ts", "evaluations", "evaluations")
    generate_file(_jobs, _OUT / "jobs.ts", "jobs", "jobs")
    generate_file(
        _sse,
        _OUT / "sse-events.ts",
        "sse_events",
        "sse-events",
        discriminated_union=("type", _sse.SseEvent),
    )


if __name__ == "__main__":
    main()
