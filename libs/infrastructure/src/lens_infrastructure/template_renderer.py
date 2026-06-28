"""Jinja2-based :class:`TemplateRendererPort` implementation.

Three default templates (``change.txt``, ``error.txt``, ``no_change.txt``)
are loaded from disk under
``libs/infrastructure/src/lens_infrastructure/notify/templates/`` and
rendered with the context variables documented alongside the notifier
contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from lens_application.pipeline import (
    RenderedMessage,
    TemplateRendererPort,
)

__all__ = ["DEFAULT_TEMPLATES_DIR", "JinjaTemplateRenderer"]


DEFAULT_TEMPLATES_DIR: Path = Path(__file__).parent / "notify" / "templates"


class JinjaTemplateRenderer(TemplateRendererPort):
    """A Jinja2-backed :class:`TemplateRendererPort`.

    The renderer is strict (``StrictUndefined``) so a missing context
    variable surfaces as an error during rendering rather than silently
    producing ``""``.
    """

    def __init__(self, templates_dir: Path | None = None) -> None:
        directory = templates_dir or DEFAULT_TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(directory)),
            autoescape=False,
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )

    def render(
        self,
        *,
        template_name: str,
        context: dict[str, Any],
    ) -> RenderedMessage:
        template = self._env.get_template(template_name)
        body = template.render(**context)
        subject = self._subject_from(body, context)
        return RenderedMessage(
            subject=subject,
            body=body,
            template=template_name,
        )

    @staticmethod
    def _subject_from(body: str, context: dict[str, Any]) -> str:
        for line in body.splitlines():
            if line.startswith("Subject:"):
                rendered = line[len("Subject:") :].strip()
                try:
                    from jinja2 import Environment

                    return Environment().from_string(rendered).render(**context)
                except Exception:
                    return rendered
        return "lens notification"
