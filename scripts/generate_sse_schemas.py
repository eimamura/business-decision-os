#!/usr/bin/env python3
"""Generate packages/schemas-ts/src/sse-events.ts from packages/schemas/sse_events.py.

packages/schemas/sse_events.py is the Single Source of Truth for SSE event schemas.
This script derives the TypeScript / Zod equivalent automatically.

Usage:
    uv run python scripts/generate_sse_schemas.py
    make codegen
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path
from typing import Annotated, Any, Literal, Union, get_args, get_origin
from uuid import UUID

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402, I001
import packages.schemas.sse_events as _mod  # noqa: E402


# ---------------------------------------------------------------------------
# Type → Zod expression
# ---------------------------------------------------------------------------

def _zod(annotation: Any) -> str:
    """Return the Zod expression string for a Python type annotation."""

    # Unwrap Annotated[X, ...]
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Union / Optional  (both `X | Y` syntax and `Union[X, Y]`)
    is_new_union = hasattr(_types, "UnionType") and isinstance(annotation, _types.UnionType)
    if origin is Union or is_new_union:
        non_none = [a for a in args if a is not type(None)]
        has_none = type(None) in args
        if len(non_none) == 1:
            base = _zod(non_none[0])
            return f"{base}.nullable().optional()" if has_none else base
        branches = ", ".join(_zod(a) for a in non_none)
        base = f"z.union([{branches}])"
        return f"{base}.nullable().optional()" if has_none else base

    # Literal
    if origin is Literal:
        if len(args) == 1:
            v = args[0]
            ts_val = f'"{v}"' if isinstance(v, str) else str(v).lower()
            return f"z.literal({ts_val})"
        vals = ", ".join(f'"{a}"' if isinstance(a, str) else str(a).lower() for a in args)
        return f"z.enum([{vals}])"

    # list[X]
    if origin is list:
        inner = _zod(args[0]) if args else "z.unknown()"
        return f"z.array({inner})"

    # dict[K, V]  →  z.record(z.unknown())
    if origin is dict:
        return "z.record(z.unknown())"

    # Nested Pydantic model → reference its generated schema
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return f"{annotation.__name__}Schema"

    # Scalars
    _SCALAR: dict[Any, str] = {
        str: "z.string()",
        int: "z.number().int()",
        float: "z.number()",
        bool: "z.boolean()",
        UUID: "z.string()",
        Any: "z.unknown()",
    }
    if annotation in _SCALAR:
        return _SCALAR[annotation]

    return "z.unknown()"


# ---------------------------------------------------------------------------
# BaseModel → Zod object
# ---------------------------------------------------------------------------

def _model_to_zod_object(cls: type[BaseModel]) -> str:
    lines = ["z.object({"]
    for name, field in cls.model_fields.items():
        zod_expr = _zod(field.annotation)
        lines.append(f"  {name}: {zod_expr},")
    lines.append("})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Collect models and union members from the module
# ---------------------------------------------------------------------------

def _collect_models() -> list[type[BaseModel]]:
    """Return all BaseModel subclasses defined in sse_events.py, in definition order."""
    seen: dict[str, type[BaseModel]] = {}
    for name, obj in vars(_mod).items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
            and obj.__module__ == _mod.__name__
        ):
            seen[name] = obj
    return list(seen.values())


def _union_members() -> list[type[BaseModel]]:
    """Return the ordered list of models in the SseEvent discriminated union."""
    sse_type = _mod.SseEvent
    # SseEvent = Annotated[Union[M1, M2, ...], Field(discriminator="type")]
    annotated_args = get_args(sse_type)
    if not annotated_args:
        return []
    union_args = get_args(annotated_args[0])
    return [a for a in union_args if isinstance(a, type) and issubclass(a, BaseModel)]


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

_HEADER = """\
import { z } from "zod";

// AUTO-GENERATED — do not edit by hand.
// Single Source of Truth: packages/schemas/sse_events.py
// Regenerate:  make codegen
"""


def generate() -> str:
    models = _collect_models()
    members = _union_members()

    lines = [_HEADER]

    for cls in models:
        schema_name = f"{cls.__name__}Schema"
        zod_body = _model_to_zod_object(cls)
        lines.append(f"export const {schema_name} = {zod_body};\n")

    if members:
        member_list = "\n  ".join(f"{m.__name__}Schema," for m in members)
        lines.append(
            f'export const SseEventSchema = z.discriminatedUnion("type", [\n'
            f"  {member_list}\n"
            f"]);\n"
        )
        lines.append("export type SseEvent = z.infer<typeof SseEventSchema>;")

    return "\n".join(lines) + "\n"


def main() -> None:
    out = ROOT / "packages/schemas-ts/src/sse-events.ts"
    content = generate()
    out.write_text(content)
    print(f"Generated {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
