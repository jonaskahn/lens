"""Crawler / pipeline / broker / storage ports.

The crawl pipeline (L0-L5 subset) is implemented as a thin orchestrator
that consumes these protocols. The orchestrator is the only piece that
knows the level order; the ports are unaware of each other.

The current implementation wires L0 (304 short-circuit), L1 (raw
fingerprint), and L5 (significance rules). L2-L4 are stubbed; they will
expand alongside ``SiteProfile``.

The notification ports are :class:`NotifierPort`,
:class:`TemplateRendererPort`, :class:`EventConsumerPort`, and the
:class:`NotificationLogRepository` protocol lives in
:mod:`lens_application.ports`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from lens_domain.entities import Change, Channel, Snapshot, Url
from lens_domain.value_objects import (
    ChangeClassification,
    ContentHash,
    CrawlConfig,
    DiffConfig,
    DiffSummary,
    ZoneChangeObservation,
    ZoneSelector,
    ZoneTextDelta,
)

__all__ = [
    "BlobStoragePort",
    "ChangeClassifierPort",
    "ChangeDetectionResult",
    "ChannelSecretProvider",
    "ContentProcessingPipeline",
    "CrawlerPort",
    "DifferPort",
    "EmbeddingPort",
    "EmbeddingScorerPort",
    "EventConsumerPort",
    "EventPublisherPort",
    "HtmlNormalizerPort",
    "LearnedZoneExtractorPort",
    "LockPort",
    "NotificationLogRepository",
    "NotifierPort",
    "PipelineContext",
    "PipelineResult",
    "RawFetchResult",
    "RenderedMessage",
    "SemanticScorerPort",
    "SendResult",
    "SiteProfileRepository",
    "StoredCheckState",
    "TaskPublisherPort",
    "TaskSubscriberPort",
    "TemplateClassifierPort",
    "TemplateClusterPort",
    "TemplateFingerprintPort",
    "TemplateRendererPort",
    "ZoneExtractorPort",
]


@dataclass(frozen=True, slots=True)
class RawFetchResult:
    """The output of one fetch from a :class:`CrawlerPort`."""

    html: str
    http_status: int
    byte_size: int
    fetched_at: datetime
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """Return True when the fetch returned HTML and no error string."""
        return self.error is None and 200 <= self.http_status < 400


class CrawlerPort(Protocol):
    """Fetch a URL and return its raw HTML + transport metadata."""

    async def fetch(self, url: str, config: CrawlConfig) -> RawFetchResult: ...


@dataclass(frozen=True, slots=True)
class NormalizedContent:
    """The output of an :class:`HtmlNormalizerPort` run."""

    text: str
    hash: ContentHash


class HtmlNormalizerPort(Protocol):
    """Normalize raw HTML to a stable plain-text representation."""

    async def normalize(self, html: str, config: DiffConfig) -> NormalizedContent: ...


@dataclass(frozen=True, slots=True)
class DiffResult:
    """A line-based diff plus the persisted unified-diff blob key."""

    summary: DiffSummary
    diff_ref: str
    unified_diff: str


class DifferPort(Protocol):
    """Compute a unified diff between previous and current normalized text."""

    async def diff(
        self,
        previous: str,
        current: str,
        config: DiffConfig,
        change_id: UUID,
        blob_storage: BlobStoragePort,
    ) -> DiffResult: ...


class BlobStoragePort(Protocol):
    """Key-addressable blob storage for HTML snapshots and full diffs."""

    async def put(self, key: str, data: bytes) -> str: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


@dataclass(frozen=True, slots=True)
class CrawlTask:
    """A crawl-task message published to the broker."""

    url_id: UUID
    task_id: str
    scheduled_slot: datetime
    reason: str = "scheduled"


class TaskPublisherPort(Protocol):
    """Publish a :class:`CrawlTask` to the broker."""

    async def publish_crawl_task(self, task: CrawlTask) -> None: ...


class TaskSubscriberPort(Protocol):
    """Subscribe to :class:`CrawlTask` messages and dispatch a handler."""

    async def start(
        self,
        handler: Any,
        *,
        prefetch: int = 1,
    ) -> None: ...

    async def stop(self) -> None: ...


class LockPort(Protocol):
    """A distributed lock with safe release semantics.

    The :meth:`acquire` method returns a non-empty token on success or
    an empty string if the lock is already held. :meth:`release` only
    deletes the key when the supplied token matches.
    """

    async def acquire(self, key: str, *, ttl_seconds: int, token: str) -> str: ...
    async def release(self, key: str, token: str) -> None: ...
    async def renew(self, key: str, token: str, *, ttl_seconds: int) -> bool: ...


class EventPublisherPort(Protocol):
    """Publish an event to the broker (used by the outbox relay)."""

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
    ) -> None: ...


class EventConsumerPort(Protocol):
    """Subscribe to events on a broker and dispatch a handler."""

    async def start(
        self,
        handler: Any,
        *,
        prefetch: int = 1,
    ) -> None: ...

    async def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class SendResult:
    """The outcome of a single :class:`NotifierPort.send` call."""

    success: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    """A rendered notification body ready for transport."""

    subject: str
    body: str
    template: str = ""


class NotifierPort(Protocol):
    """Send a rendered message to a single :class:`Channel`.

    Implementations decrypt the channel's Apprise URL at the moment of
    send; the URL never reaches a log statement.
    """

    async def send(
        self,
        *,
        channel_kind: str,
        apprise_url: str,
        message: RenderedMessage,
    ) -> SendResult: ...


class TemplateRendererPort(Protocol):
    """Render a Jinja2 template with a context dict."""

    def render(
        self,
        *,
        template_name: str,
        context: dict[str, Any],
    ) -> RenderedMessage: ...


class ChannelSecretProvider(Protocol):
    """Adapter that returns a channel's decrypted Apprise URL."""

    def apprise_url_for(self, channel: Channel) -> str: ...


class NotificationLogRepository(Protocol):
    """Persistence boundary for the per-channel dedup log."""

    async def seen(
        self,
        *,
        event_id: UUID,
        channel_id: UUID,
    ) -> bool: ...

    async def record(
        self,
        *,
        event_id: UUID,
        channel_id: UUID,
        status: str,
        error: str | None,
        sent_at: datetime,
    ) -> bool: ...


# ---------------------------------------------------------------------------
# L2-L4 pipeline ports (07 §6)
# ---------------------------------------------------------------------------


class SiteProfileRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.SiteProfile`."""

    async def get(self, domain: str, url: str) -> Any: ...

    async def upsert(self, profile: Any) -> None: ...

    async def list_by_domain(self, domain: str) -> list[Any]: ...


class TemplateFingerprintPort(Protocol):
    """Extract a canonical DOM skeleton from raw HTML."""

    def extract_skeleton(self, html: str) -> str: ...

    def hash_skeleton(self, skeleton: str) -> str: ...


class ZoneExtractorPort(Protocol):
    """Apply :class:`ZoneSelector` selectors to HTML and return zone texts."""

    def extract(
        self,
        html: str,
        selectors: list[ZoneSelector],
    ) -> dict[str, str]: ...


class SemanticScorerPort(Protocol):
    """Score the significance of a text change between two snapshots.

    Returns a float in ``[0.0, 1.0]`` where 0.0 means identical and
    1.0 means completely different.
    """

    def score(self, old_text: str, new_text: str) -> float: ...

    def score_zone_weighted(
        self,
        old_text: str,
        new_text: str,
        zone_weight: float,
    ) -> float: ...


class TemplateClassifierPort(Protocol):
    """Classify a page's platform/template from raw HTML via regex patterns.

    Returns a template class name (e.g. ``"ecommerce/woocommerce"``)
    or ``None`` when no known class matches.
    """

    def classify(self, html: str) -> str | None: ...

    def zones_for_class(self, class_name: str) -> list[ZoneSelector]: ...


# ---------------------------------------------------------------------------
# Pipeline data classes (07 §5)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StoredCheckState:
    """The persisted state from the previous check for this URL."""

    url_id: UUID
    raw_md5: str | None = None
    filter_config_hash: str | None = None
    last_etag: str | None = None
    last_modified: str | None = None
    zone_hashes: dict[str, str] = field(default_factory=dict)
    zone_texts: dict[str, str] = field(default_factory=dict)
    previous_cleaned_text: str = ""
    last_check_at: datetime | None = None
    profile_id: UUID | None = None


class PipelineResult(StrEnum):
    """Outcome of a single run through the content-processing pipeline."""

    SKIP = "skip"
    CHANGE_DETECTED = "change_detected"
    ERROR = "error"


@dataclass(slots=True)
class ChangeDetectionResult:
    """A serializable view of a pipeline outcome."""

    url_id: UUID
    result: PipelineResult
    skip_reason: str | None
    significant: bool
    semantic_score: float | None
    added_count: int
    removed_count: int
    diff_ref: str | None
    snapshot_id: UUID | None
    previous_snapshot_id: UUID | None
    levels_reached: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PipelineContext:
    """The shared context threaded through the pipeline levels."""

    url_id: UUID
    address: str
    crawl_config: CrawlConfig
    diff_config: DiffConfig
    raw_html: str
    raw_bytes: bytes
    http_status: int
    http_headers: dict[str, str] = field(default_factory=dict)
    stored: StoredCheckState = field(
        default_factory=lambda: StoredCheckState(url_id=UUID(int=0)),
    )
    raw_md5: str = ""
    filter_config_hash: str = ""
    skeleton_hash: str = ""
    profile: Any = None
    current_zone_hashes: dict[str, str] = field(default_factory=dict)
    changed_zones: dict[str, str] = field(default_factory=dict)
    scored_zone_texts: dict[str, ZoneTextDelta] = field(default_factory=dict)
    cleaned_text: str = ""
    semantic_score: float = 0.0
    diff_ref: str | None = None
    change_id: UUID | None = None
    snapshot_id: UUID | None = None
    previous_snapshot_id: UUID | None = None
    snapshot: Snapshot | None = None
    change: Change | None = None
    levels_reached: list[str] = field(default_factory=list)
    result: PipelineResult | None = None
    skip_reason: str | None = None
    escalate_to_ai: bool = False
    escalation_reasons: list[str] = field(default_factory=list)
    embedding_signals: dict[str, Any] = field(default_factory=dict)


class ContentProcessingPipeline(Protocol):
    """The thin orchestrator over the L0-L5 pipeline ports."""

    async def process(self, ctx: PipelineContext) -> ChangeDetectionResult: ...


@runtime_checkable
class ContentProcessingPipelineFactory(Protocol):
    """A factory the worker can call to build a per-URL pipeline context."""

    def build_context(self, url: Url, raw: RawFetchResult) -> PipelineContext: ...


# ---------------------------------------------------------------------------
# AI enrichment ports (12-ai-enrichment-layer.md §2)
# ---------------------------------------------------------------------------


class EmbeddingPort(Protocol):
    """Produce dense vector embeddings for a batch of texts.

    Implementations may use a local sentence-transformers model or an
    OpenAI-compatible ``/v1/embeddings`` HTTP endpoint.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def model_id(self) -> str: ...

    @property
    def dim(self) -> int: ...


class EmbeddingScorerPort(Protocol):
    """Compute a semantic distance between two texts using embeddings.

    Returns ``1 - cosine_similarity(embed(old), embed(new))``, clamped
    to ``[0.0, 1.0]``. Uses :class:`EmbeddingPort` + an internal cache.
    """

    async def semantic_distance(self, old_text: str, new_text: str) -> float: ...


@dataclass(frozen=True, slots=True)
class ClassifyRequest:
    """A single classification request emitted by the escalation gate."""

    change_id: UUID
    prev_text: str
    curr_text: str
    zone_name: str = ""
    template_class: str | None = None
    few_shot_examples: list[dict[str, Any]] = field(default_factory=list)


class ChangeClassifierPort(Protocol):
    """Run an LLM on a changed-zone diff and return validated structured output.

    Implementations MUST use constrained/guided decoding so the result
    always parses without manual JSON repair.
    """

    async def classify(self, request: ClassifyRequest) -> ChangeClassification: ...


# ---------------------------------------------------------------------------
# Auto-learning ports (12-ai-enrichment-layer.md §6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ZoneChangeHistory:
    """Aggregated per-zone change observations for a profile or domain.

    Fed to :class:`LearnedZoneExtractorPort` to derive noise-vs-signal
    zone selectors and per-zone thresholds.
    """

    profile_id: UUID | None = None
    domain: str = ""
    observations: list[ZoneChangeObservation] = field(default_factory=list)
    total_checks: int = 0
    total_changes: int = 0


class LearnedZoneExtractorPort(Protocol):
    """Mine per-zone change frequency/type to classify noise vs signal zones.

    Implements ``07`` §12 open decision #6. Implementations consume
    :class:`ZoneChangeHistory` from the DB and emit learned
    :class:`ZoneSelector` values with weights and noise flags.
    """

    async def learn_zones(
        self,
        history: ZoneChangeHistory,
    ) -> list[ZoneSelector]: ...


class TemplateClusterPort(Protocol):
    """Cluster URLs into template profiles and detect structural drift.

    Featurizes pages by DOM-skeleton shingles and clusters (HDBSCAN);
    returns cluster assignments and drift events per profile.
    """

    async def cluster(
        self,
        domain: str,
        skeleton_hashes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]: ...
