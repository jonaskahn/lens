"""Immutable, self-validating value objects.

All VOs are Pydantic ``BaseModel`` subclasses with ``frozen=True`` and
``extra="forbid"``; validators run on construction so an invalid value
raises :class:`lens_common.errors.DomainError` immediately.
"""

from __future__ import annotations

import re
from typing import Any, Final
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from lens_common.errors import DomainError
from lens_domain.enums import ChangeType, SignificanceRuleType, TriggerType
from lens_domain.errors import (
    InvalidAddress,
    InvalidHostname,
    InvalidInterval,
    InvalidPoliteness,
)

__all__ = [
    "Address",
    "ChangeClassification",
    "ChangeLabel",
    "ContentHash",
    "CrawlConfig",
    "DiffConfig",
    "DiffSummary",
    "EmbeddingSignal",
    "Hostname",
    "Interval",
    "NotificationRouting",
    "Politeness",
    "SignificanceRule",
    "ZoneChangeObservation",
    "ZoneSelector",
    "ZoneTextDelta",
]


class _FrozenModel(BaseModel):
    """Common base for all VOs: frozen, forbid extras, validate defaults.

    Pydantic's ``ValidationError`` is re-raised as a :class:`DomainError` so
    callers can use a single exception type for invariant violations across
    every layer of the application.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as exc:
            first = exc.errors()[0] if exc.errors() else {"msg": "validation failed"}
            raise DomainError(
                str(first.get("msg", "validation failed")),
                details={"errors": exc.errors()},
            ) from exc


_HOST_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.?$",
)


class Hostname(_FrozenModel):
    """A normalised, lowercased DNS hostname (no scheme, no path)."""

    value: str = Field(min_length=1, max_length=253)

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        candidate = raw.strip().lower().rstrip(".")
        if not candidate:
            raise InvalidHostname("hostname must not be empty")
        if not _HOST_RE.match(candidate):
            raise InvalidHostname(f"invalid hostname: {raw!r}")
        return candidate


class Address(_FrozenModel):
    """An absolute HTTP(S) URL whose host is parseable."""

    value: str = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        candidate = raw.strip()
        if not candidate:
            raise InvalidAddress("address must not be empty")
        try:
            parsed = urlparse(candidate)
        except ValueError as exc:
            raise InvalidAddress(f"unparseable address: {raw!r}") from exc
        if parsed.scheme not in {"http", "https"}:
            raise InvalidAddress(
                f"address must use http or https scheme: {raw!r}",
            )
        if not parsed.hostname:
            raise InvalidAddress(f"address is missing a host: {raw!r}")
        return candidate

    @property
    def host(self) -> str:
        """Return the lowercased hostname of the address."""
        return Hostname(value=urlparse(self.value).hostname or "").value

    @property
    def scheme(self) -> str:
        """Return the URL scheme (http or https)."""
        return urlparse(self.value).scheme

    @property
    def path(self) -> str:
        """Return the URL path (may be empty)."""
        return urlparse(self.value).path


class ContentHash(_FrozenModel):
    """A typed content hash; only sha256 is supported in this version."""

    algo: str = Field(default="sha256")
    hex: str = Field(min_length=1)

    @field_validator("algo")
    @classmethod
    def _validate_algo(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"sha256"}:
            raise ValueError(f"unsupported hash algorithm: {value!r}")
        return normalized

    @field_validator("hex")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        candidate = value.strip().lower()
        if len(candidate) != 64 or any(c not in "0123456789abcdef" for c in candidate):
            raise ValueError(f"hash hex must be 64 lowercase hex chars: {value!r}")
        return candidate

    def __str__(self) -> str:
        return f"{self.algo}:{self.hex}"


class CrawlConfig(_FrozenModel):
    """How a URL should be fetched by the crawler."""

    selector: str | None = None
    wait_for: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    proxy: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    js_enabled: bool = True


class SignificanceRule(_FrozenModel):
    """L5 rule applied during change significance evaluation."""

    type: SignificanceRuleType
    pattern: str = Field(min_length=1)
    is_regex: bool = False

    @model_validator(mode="after")
    def _validate(self) -> SignificanceRule:
        if self.is_regex:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(
                    f"significance rule pattern does not compile: {exc}",
                ) from exc
        return self


class DiffConfig(_FrozenModel):
    """Diffing configuration: ignore lists, rules, thresholds."""

    ignore_regexes: list[str] = Field(default_factory=list)
    ignore_selectors: list[str] = Field(default_factory=list)
    significance_rules: list[SignificanceRule] = Field(default_factory=list)
    min_text_length: int = Field(default=10, ge=0)
    semantic_threshold: float = Field(default=0.05, ge=0.0, le=1.0)

    @field_validator("ignore_regexes")
    @classmethod
    def _compile_regexes(cls, raw: list[str]) -> list[str]:
        for pattern in raw:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"ignore_regex does not compile ({pattern!r}): {exc}",
                ) from exc
        return raw


class DiffSummary(_FrozenModel):
    """A pure representation of a text diff: counts only (no rendering)."""

    added_count: int = Field(default=0, ge=0)
    removed_count: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        """Return the sum of added and removed lines."""
        return self.added_count + self.removed_count

    @property
    def is_empty(self) -> bool:
        """Return True when no lines were added and no lines were removed."""
        return self.added_count == 0 and self.removed_count == 0


class Politeness(_FrozenModel):
    """Politeness controls: max concurrent fetches and minimum delay."""

    max_concurrency: int = Field(default=2)
    min_delay_ms: int = Field(default=1000)

    @model_validator(mode="after")
    def _validate(self) -> Politeness:
        if self.max_concurrency < 1:
            raise InvalidPoliteness("max_concurrency must be >= 1")
        if self.min_delay_ms < 0:
            raise InvalidPoliteness("min_delay_ms must be >= 0")
        return self


class Interval(_FrozenModel):
    """A polling interval in seconds, floored by the global minimum."""

    seconds: int = Field(ge=1)
    global_minimum: int = Field(default=300, ge=1)

    @model_validator(mode="after")
    def _validate(self) -> Interval:
        if self.seconds < self.global_minimum:
            raise InvalidInterval(
                f"interval {self.seconds}s is below the global minimum {self.global_minimum}s",
            )
        return self


class NotificationRouting(_FrozenModel):
    """Notification routing override: explicit channels + trigger set."""

    channel_ids: list[str] = Field(default_factory=list)
    triggers: set[TriggerType] = Field(default_factory=set)

    @field_validator("channel_ids")
    @classmethod
    def _unique_channel_ids(cls, raw: list[str]) -> list[str]:
        if len(raw) != len(set(raw)):
            raise ValueError("channel_ids must be unique")
        return raw

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict (triggers serialised as sorted list)."""
        return {
            "channel_ids": list(self.channel_ids),
            "triggers": sorted(t.value for t in self.triggers),
        }


class ZoneSelector(_FrozenModel):
    """A CSS selector that identifies a named zone within an HTML page.

    Attributes:
        name: Unique zone identifier within a SiteProfile (e.g. ``price``, ``navigation``).
        css_selector: CSS selector string used to extract matching elements.
        weight: Multiplier for the zone's semantic score contribution. Higher
            values amplify the importance of changes in this zone. Zero
            marks noise zones that are ignored for change detection.
        is_noise: When True, changes in this zone are discarded entirely;
            the zone contributes 0.0 to the aggregate semantic score.
    """

    name: str = Field(min_length=1)
    css_selector: str = Field(min_length=1)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    is_noise: bool = False


class ZoneTextDelta(_FrozenModel):
    """Describes the text change detected in a single zone between checks.

    Attributes:
        zone_name: Name of the zone (matches a :class:`ZoneSelector` name).
        previous_text: Text content from the previous check.
        current_text: Text content from the current check.
        zone_score: Weighted semantic score for this zone (``semantic_score * weight``).
    """

    zone_name: str = Field(min_length=1)
    previous_text: str = ""
    current_text: str = ""
    zone_score: float = Field(default=0.0, ge=0.0, le=10.0)


# ---------------------------------------------------------------------------
# AI enrichment value objects (12-ai-enrichment-layer.md sections 2-4)
# ---------------------------------------------------------------------------


class ChangeClassification(_FrozenModel):
    """LLM-produced classification of a detected change (L6 AI tier).

    Attributes:
        change_type: Category of the change (content, price, stock, etc.).
        is_meaningful: Whether this change is meaningful to users.
        severity: 1 (low) to 5 (critical).
        summary: Human-readable summary, <= 280 chars.
        extracted_fields: Key-value pairs extracted by the LLM
            (e.g. ``{"price_old": "99.00", "price_new": "79.00"}``).
        confidence: LLM confidence score in [0.0, 1.0].
        model_id: Identifier of the LLM that produced this classification.
        tokens_used: LLM response token count (0 when unavailable).
        latency_ms: Wall-clock ms for the LLM call (0 when unavailable).
    """

    change_type: ChangeType
    is_meaningful: bool
    severity: int = Field(default=1, ge=1, le=5)
    summary: str = Field(default="", max_length=280)
    extracted_fields: dict[str, str | None] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model_id: str = Field(default="")
    tokens_used: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)


class EmbeddingSignal(_FrozenModel):
    """Dual-signal embedding data captured at L4 for a single zone.

    Attributes:
        lexical: Jaccard token distance from the lexical scorer [0, 1].
        semantic: Cosine distance from the embedding scorer [0, 1].
        disagree: True when the lexical and semantic scores diverge enough
            to trigger an escalation; computed as
            ``abs(lexical - semantic) >= AI_SIGNAL_DISAGREE_DELTA``.
    """

    lexical: float = Field(default=0.0, ge=0.0, le=1.0)
    semantic: float = Field(default=0.0, ge=0.0, le=1.0)
    disagree: bool = False


# ---------------------------------------------------------------------------
# Auto-learning value objects (12-ai-enrichment-layer.md §6)
# ---------------------------------------------------------------------------


class ChangeLabel(_FrozenModel):
    """A human or LLM label attached to a change for learning/eval.

    Attributes:
        change_id: The change this label applies to.
        is_change: Whether a real change occurred.
        is_meaningful: Whether the change is meaningful (None if unknown).
        change_type: The type of change (None if unknown).
        labeled_by: Who produced this label (human, llm, rule).
    """

    change_id: UUID
    is_change: bool
    is_meaningful: bool | None = None
    change_type: str | None = None
    labeled_by: str


class ZoneChangeObservation(_FrozenModel):
    """Per-zone change observation mined from history for learning.

    Attributes:
        zone_name: Name of the observed zone.
        check_count: Total checks for this zone.
        change_count: Number of checks where the zone changed.
        avg_semantic_score: Mean semantic score when the zone changed.
        labeled_changes: Number of changes with a label for this zone.
        labeled_meaningful: Number of labeled changes marked meaningful.
    """

    zone_name: str = Field(min_length=1)
    check_count: int = Field(default=0, ge=0)
    change_count: int = Field(default=0, ge=0)
    avg_semantic_score: float = Field(default=0.0, ge=0.0, le=1.0)
    labeled_changes: int = Field(default=0, ge=0)
    labeled_meaningful: int = Field(default=0, ge=0)
