"""Turn Pydantic models into JSON schemas that chat APIs accept.

Pydantic emits $refs, titles, defaults and formats that some providers reject in
structured-output or function schemas. We inline the refs and drop the rest;
Pydantic still validates the full model (ranges, datetimes) on the way back in.
"""

from typing import Any

from pydantic import BaseModel

from investigator.tools.catalog import ToolSpec

_DROP = {"title", "default", "format", "minimum", "maximum", "exclusiveMinimum",
         "exclusiveMaximum", "minItems", "maxItems"}


def llm_schema(model: type[BaseModel], *, strict: bool) -> dict[str, Any]:
    """strict=True: every property required, no extra keys (structured output mode)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = dict(defs[node["$ref"].rsplit("/", 1)[-1]])
            target.update({k: v for k, v in node.items() if k != "$ref"})
            return walk(target)
        out = {}
        for key, value in node.items():
            if key == "properties":  # field names, not keywords: keep them all
                out[key] = {name: walk(sub) for name, sub in value.items()}
            elif key not in _DROP:
                out[key] = walk(value)
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            if strict:
                out["required"] = list(out["properties"])
        return out

    return walk(schema)


def tool_definition(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": " ".join((spec.input.__doc__ or "").split()),
            "parameters": {k: v for k, v in llm_schema(spec.input, strict=False).items()
                           if k != "description"},
        },
    }
