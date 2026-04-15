from __future__ import annotations

import os
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import yaml

try:
    from server.qmd_runtime import qmd_update
except ImportError:  # pragma: no cover - current tree may not ship the qmd module yet
    def qmd_update(vault_path: Path) -> dict[str, Any]:
        return {"ok": False, "error": "qmd runtime unavailable"}


_PAGE_DIRS: dict[str, tuple[str, ...]] = {
    "paper": ("wiki", "papers"),
    "concept": ("wiki", "concepts"),
    "method": ("wiki", "methods"),
    "topic": ("wiki", "topics"),
    "conversation": ("insights", "conversations"),
}

_V3_LAYOUT_DIRS: tuple[tuple[str, ...], ...] = (
    ("inbox",),
    ("raw", "evidence"),
    ("wiki", "papers"),
    ("wiki", "concepts"),
    ("wiki", "methods"),
    ("wiki", "topics"),
    ("insights", "conversations"),
    (".state",),
)


def _ensure_v3_layout(vault_path: Path) -> None:
    for parts in _V3_LAYOUT_DIRS:
        (vault_path.joinpath(*parts)).mkdir(parents=True, exist_ok=True)


def _target_path(vault_path: Path, page_type: str, target: str) -> Path:
    page_dirs = _PAGE_DIRS.get(page_type)
    if page_dirs is None:
        raise ValueError(
            f"unsupported page_type: {page_type}. Expected one of: "
            + ", ".join(sorted(_PAGE_DIRS))
        )
    return vault_path.joinpath(*page_dirs, f"{target}.md")


def _render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    stream = StringIO()
    stream.write("---\n")
    stream.write(
        yaml.safe_dump(
            frontmatter,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).strip()
    )
    stream.write("\n")
    stream.write("---\n\n")
    stream.write(body.rstrip())
    stream.write("\n")
    return stream.getvalue()


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


def upsert_wiki_page_v3(
    vault_path: Path,
    page_type: str,
    target: str,
    frontmatter: dict,
    body: str,
) -> dict[str, Any]:
    target = target.strip()
    if not target:
        return {"ok": False, "error": "target is required", "warnings": []}
    if any(sep in target for sep in ("/", "\\", "..")):
        return {"ok": False, "error": "target must not contain path separators", "warnings": []}

    _ensure_v3_layout(vault_path)

    try:
        path = _target_path(vault_path, page_type, target)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "warnings": []}

    payload = dict(frontmatter or {})
    payload.setdefault("type", page_type)

    try:
        _atomic_write_text(path, _render_markdown(payload, body))
    except Exception as exc:  # pragma: no cover - defensive path
        return {"ok": False, "error": str(exc), "warnings": []}

    warnings: list[str] = []
    try:
        update_result = qmd_update(vault_path)
    except Exception as exc:  # pragma: no cover - defensive path
        update_result = {"ok": False, "error": str(exc)}

    if not update_result.get("ok", False):
        warning = str(update_result.get("error") or "qmd update failed")
        warnings.append(warning)

    return {"ok": True, "path": str(path), "warnings": warnings}
