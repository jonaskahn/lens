"""vLLM classifier adapter for the L6 AI tier.

Implements :class:`lens_application.pipeline.ChangeClassifierPort` via an
OpenAI-compatible HTTP endpoint (vLLM, TEI, Ollama, or any hosted API).
Uses guided JSON decoding to guarantee valid ``ChangeClassification`` output.
"""

from __future__ import annotations

import json
from typing import Any

from lens_application.pipeline import ClassifyRequest
from lens_domain.value_objects import ChangeClassification

_SYSTEM_PROMPT = """You are a website change classifier. Given a diff of a changed zone on a web page, classify the change.

Output a JSON object with these fields:
- change_type: one of "content", "price", "stock", "legal", "layout", "cosmetic", "other"
- is_meaningful: true if a human user would care about this change, false if it's noise/cosmetic
- severity: 1-5 (1=trivial, 5=critical)
- summary: short human-readable summary (max 280 chars)
- extracted_fields: key-value map of extracted data (e.g. {"price_old": "99.00", "price_new": "79.00"})
- confidence: float 0.0-1.0 indicating your confidence in this classification
"""

_USER_PROMPT = """Zone: {zone_name}
Template class: {template_class}

Previous text:
---
{prev_text}
---

Current text:
---
{curr_text}
---

Classify this change."""


class VLLMClassifierAdapter:
    """Implements :class:`lens_application.pipeline.ChangeClassifierPort`.

    Communicates with a vLLM or OpenAI-compatible server via the standard
    ``/v1/chat/completions`` endpoint. Uses the ``response_format`` /
    ``guided_json`` mechanism for structured output.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "not-needed",
        model: str = "Qwen2.5-7B-Instruct",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=self._timeout,
            )
        except ImportError:
            self._client = _DummyLLMClient(self._model)
        return self._client

    async def classify(self, request: ClassifyRequest) -> ChangeClassification:
        import time

        client = self._get_client()
        if isinstance(client, _DummyLLMClient):
            return client.classify(request)

        user_prompt = _USER_PROMPT.format(
            zone_name=request.zone_name or "unknown",
            template_class=request.template_class or "generic",
            prev_text=request.prev_text[:2000],
            curr_text=request.curr_text[:2000],
        )

        json_schema = _build_json_schema()

        t0 = time.monotonic()
        response = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "change_classification", "schema": json_schema},
            },
            temperature=0.1,
            max_tokens=512,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        usage = getattr(response, "usage", None)
        tokens_used = getattr(usage, "total_tokens", 0) if usage is not None else 0

        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        return self._parse_classification(data, tokens_used=tokens_used, latency_ms=latency_ms)

    @staticmethod
    def _parse_classification(
        data: dict[str, Any],
        *,
        tokens_used: int = 0,
        latency_ms: int = 0,
    ) -> ChangeClassification:
        from lens_domain.enums import ChangeType

        change_type_str = str(data.get("change_type", "other")).lower()
        valid_types = {t.value for t in ChangeType}
        if change_type_str not in valid_types:
            change_type_str = "other"

        return ChangeClassification(
            change_type=ChangeType(change_type_str),
            is_meaningful=bool(data.get("is_meaningful", False)),
            severity=max(1, min(5, int(data.get("severity", 1)))),
            summary=str(data.get("summary", ""))[:280],
            extracted_fields={
                k: str(v) if v is not None else None for k, v in data.get("extracted_fields", {}).items()
            },
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
            model_id="vllm:unknown",
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )


def _build_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "change_type": {
                "type": "string",
                "enum": [
                    "content",
                    "price",
                    "stock",
                    "legal",
                    "layout",
                    "cosmetic",
                    "other",
                ],
            },
            "is_meaningful": {"type": "boolean"},
            "severity": {"type": "integer", "minimum": 1, "maximum": 5},
            "summary": {"type": "string", "maxLength": 280},
            "extracted_fields": {
                "type": "object",
                "additionalProperties": {"type": ["string", "null"]},
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": [
            "change_type",
            "is_meaningful",
            "severity",
            "summary",
            "extracted_fields",
            "confidence",
        ],
    }


class _DummyLLMClient:
    """Fallback classifier for tests / no-LLM environments.

    Always returns "content" / meaningful / severity 1 / low confidence.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def classify(self, request: ClassifyRequest) -> ChangeClassification:
        from lens_domain.enums import ChangeType

        return ChangeClassification(
            change_type=ChangeType.CONTENT,
            is_meaningful=True,
            severity=1,
            summary=f"Change in zone {request.zone_name!r}",
            confidence=0.3,
            model_id=self._model,
        )

    @staticmethod
    def _build_json_schema() -> dict[str, Any]:
        return _build_json_schema()
