"""Jinja2 template renderer for Paper Distill vault notes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template by name with the given context.

    Args:
        name: Template filename (e.g. "inbox-paper.md.j2")
        context: Variables to pass to the template.

    Returns:
        Rendered markdown string.
    """
    template = _env.get_template(name)
    return template.render(**context)


def available_templates() -> list[str]:
    """List all .j2 template names in the templates directory."""
    return sorted(p.name for p in _TEMPLATES_DIR.glob("*.j2"))
