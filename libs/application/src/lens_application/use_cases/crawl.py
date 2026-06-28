"""Crawl and diff use cases.

These use cases wrap the ``ContentProcessingPipeline`` and the broker
ports. They are the only place in the application layer that orchestrates
state transitions on :class:`Url` and writes ``Snapshot`` / ``Change`` /
outbox rows in a single transaction.

The use cases accept fake ports (``CrawlerPort``, ``HtmlNormalizerPort``,
``DifferPort``, ``BlobStoragePort``, ``TaskPublisherPort``, ``LockPort``)
through their constructors so unit tests can wire doubles and exercise
the full pipeline without any real I/O.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from lens_application.dto import (
    ChangeDto,
    EnqueueCheckResult,
    ListResult,
    SnapshotDto,
    TriggerCheckInput,
    TriggerCheckResult,
)
from lens_application.errors import NotFoundError, ValidationFailed
from lens_application.pipeline import (
    BlobStoragePort,
    CrawlTask,
    DifferPort,
    EmbeddingScorerPort,
    HtmlNormalizerPort,
    LockPort,
    PipelineContext,
    PipelineResult,
    RawFetchResult,
    SemanticScorerPort,
    SiteProfileRepository,
    StoredCheckState,
    TaskPublisherPort,
    TemplateClassifierPort,
    TemplateFingerprintPort,
    ZoneExtractorPort,
)
from lens_application.ports import (
    DeadLetterRepositoryPort,
    IdempotencyPort,
    ThrottlePort,
    UnitOfWork,
)
from lens_application.use_cases._base import UseCase
from lens_application.use_cases._mapping import change_to_dto, snapshot_to_dto
from lens_domain.entities import Change, Snapshot, Url
from lens_domain.enums import EscalationReason
from lens_domain.events import ChangeNeedsEnrichment
from lens_domain.ids import ChangeId, SnapshotId
from lens_domain.services import ChangeSignificanceEvaluator
from lens_domain.value_objects import (
    ContentHash,
    CrawlConfig,
    DiffConfig,
    EmbeddingSignal,
    ZoneTextDelta,
)

__all__ = [
    "EnqueueDueUrlsUseCase",
    "GetChangeDiffBlobUseCase",
    "GetChangeDiffUseCase",
    "GetChangeUseCase",
    "GetLatestSnapshotUseCase",
    "GetSnapshotUseCase",
    "ListChangesUseCase",
    "ListSnapshotsUseCase",
    "ProcessCrawlTaskUseCase",
    "TriggerCheckUseCase",
]


# ---------------------------------------------------------------------------
# Crawl scheduling
# ---------------------------------------------------------------------------


def _task_id_for(url_id: UUID, scheduled_slot: datetime) -> str:
    """Build the idempotent ``task_id`` for a crawl task."""
    payload = f"{url_id}|{scheduled_slot.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_host(address: str) -> str:
    """Extract the hostname from a URL string for throttle keying."""
    parsed = urlparse(address)
    return parsed.hostname or address


class EnqueueDueUrlsUseCase(UseCase[dict[str, Any], EnqueueCheckResult]):
    """Claim due URLs and publish one crawl task per URL.

    The UoW is committed by the base class *after* the broker publish,
    so a crash between publish and commit is recoverable on the next tick
    (the published task is idempotent on ``task_id``).
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        publisher: TaskPublisherPort,
        *,
        batch_size: int = 100,
    ) -> None:
        super().__init__(uow_factory)
        self._publisher = publisher
        self._batch_size = batch_size

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> EnqueueCheckResult:
        now: datetime = params.get("now", uow.now())
        due_urls: list[Url] = list(
            await uow.urls.list_due(now=now, limit=self._batch_size),
        )
        enqueued: list[UUID] = []
        for url in due_urls:
            task_id = _task_id_for(url.id, url.next_due_at)
            await self._publisher.publish_crawl_task(
                CrawlTask(
                    url_id=url.id,
                    task_id=task_id,
                    scheduled_slot=url.next_due_at,
                    reason="scheduled",
                ),
            )
            url.claim(
                worker_id="scheduler",
                lease_ttl=timedelta(seconds=300),
                now=now,
            )
            await uow.urls.update(url)
            enqueued.append(url.id)
        await uow.flush()
        return EnqueueCheckResult(
            enqueued=len(enqueued),
            url_ids=enqueued,
        )


class TriggerCheckUseCase(UseCase[TriggerCheckInput, TriggerCheckResult]):
    """Enqueue an immediate crawl for a URL, category, or domain.

    Marks the target URL(s) as due-now and publishes a task for each.
    Returns the count and the list of enqueued url ids.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        publisher: TaskPublisherPort,
    ) -> None:
        super().__init__(uow_factory)
        self._publisher = publisher

    async def run(self, input_dto: TriggerCheckInput, uow: UnitOfWork) -> TriggerCheckResult:
        targets: list[Url] = await self._resolve_targets(uow, input_dto)
        enqueued: list[UUID] = []
        for url in targets:
            if not url.enabled:
                continue
            now = uow.now()
            url.mark_due(now=now)
            task_id = _task_id_for(url.id, now)
            await self._publisher.publish_crawl_task(
                CrawlTask(
                    url_id=url.id,
                    task_id=task_id,
                    scheduled_slot=now,
                    reason="manual",
                ),
            )
            await uow.urls.update(url)
            enqueued.append(url.id)
        await uow.flush()
        return TriggerCheckResult(
            enqueued=len(enqueued),
            url_ids=enqueued,
        )

    async def _resolve_targets(self, uow: UnitOfWork, input_dto: TriggerCheckInput) -> list[Url]:
        if input_dto.url_id is not None:
            url = await uow.urls.get(input_dto.url_id)
            if url is None:
                raise NotFoundError(f"url not found: {input_dto.url_id!s}")
            return [url]
        if input_dto.category_id is not None:
            return await uow.urls.list_by_category(input_dto.category_id)
        if input_dto.domain_id is not None:
            return await uow.urls.list_by_domain(input_dto.domain_id)
        raise ValidationFailed(
            "one of url_id, category_id, or domain_id is required",
        )


# ---------------------------------------------------------------------------
# Process crawl task
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _PipelineDeps:
    crawler: Any
    normalizer: HtmlNormalizerPort
    differ: DifferPort
    blob: BlobStoragePort
    lock: LockPort
    evaluator: ChangeSignificanceEvaluator
    fingerprint: TemplateFingerprintPort | None = None
    zone_extractor: ZoneExtractorPort | None = None
    scorer: SemanticScorerPort | None = None
    classifier: TemplateClassifierPort | None = None
    profile_repo: SiteProfileRepository | None = None
    embedding_scorer: EmbeddingScorerPort | None = None
    ai_enabled: bool = False
    ai_signal_disagree_delta: float = 0.35
    ai_reword_damping: float = 0.5
    ai_semantic_floor: float = 0.10
    ai_gray_band_low: float = 0.03
    ai_gray_band_high: float = 0.08


def _compute_raw_md5(raw_bytes: bytes) -> str:
    return hashlib.md5(raw_bytes, usedforsecurity=False).hexdigest()


def _filter_config_hash(crawl: CrawlConfig, diff: DiffConfig) -> str:
    """Build a hash over the effective crawl + diff config.

    When a filter config changes, L1 must re-process the URL even if the
    raw bytes are identical (07 §3 L1 critical edge case).
    """
    payload = (f"{crawl.model_dump_json()}|{diff.model_dump_json()}").encode()
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def _strip_ignore_regexes(text: str, diff_config: DiffConfig) -> str:
    if not diff_config.ignore_regexes:
        return text
    kept: list[str] = []
    for line in text.splitlines():
        if any(re.search(pattern, line) for pattern in diff_config.ignore_regexes):
            continue
        kept.append(line)
    return "\n".join(kept)


class _CrawlPipeline:
    """Orchestrator over L0-L5.

    L2-L4 are activated when the optional pipeline ports (fingerprint,
    zone_extractor, scorer, classifier, profile_repo) are wired through
    :class:`_PipelineDeps`; when absent the pipeline degrades to L0/L1/L5
    gracefully.
    """

    def __init__(self, deps: _PipelineDeps) -> None:
        self._deps = deps

    async def process(self, ctx: PipelineContext) -> Any:
        ctx.levels_reached.append("L0")
        if ctx.http_status == 304:
            return _skip(ctx, "304_not_modified")

        ctx.levels_reached.append("L1")
        ctx.raw_md5 = _compute_raw_md5(ctx.raw_bytes)
        ctx.filter_config_hash = _filter_config_hash(
            ctx.crawl_config,
            ctx.diff_config,
        )
        if ctx.raw_md5 == ctx.stored.raw_md5 and ctx.filter_config_hash == ctx.stored.filter_config_hash:
            return _skip(ctx, "raw_hash_unchanged")

        has_l2 = self._deps.fingerprint is not None
        has_l3 = has_l2 and self._deps.zone_extractor is not None
        has_l4 = has_l3 and self._deps.scorer is not None

        if has_l2:
            ctx.levels_reached.append("L2")
            self._run_l2(ctx)

        if has_l3 and ctx.profile is not None:
            ctx.levels_reached.append("L3")
            self._run_l3(ctx)
            if not ctx.changed_zones:
                return _skip(ctx, "all_zones_unchanged")

        if has_l4 and ctx.profile is not None:
            ctx.levels_reached.append("L4")
            await self._run_l4(ctx)
            if ctx.semantic_score < ctx.profile.semantic_threshold:
                return _skip(ctx, "below_semantic_threshold")

        normalized = await self._deps.normalizer.normalize(
            ctx.raw_html,
            ctx.diff_config,
        )
        cleaned = _strip_ignore_regexes(normalized.text, ctx.diff_config)
        ctx.cleaned_text = cleaned

        ctx.levels_reached.append("L5")
        significant = self._deps.evaluator.evaluate(
            cleaned,
            ctx.diff_config,
        )
        if not significant:
            return _skip(ctx, "insignificant_after_rules")

        self._evaluate_escalation_gate(ctx)

        return _change_detected(ctx)

    def _evaluate_escalation_gate(self, ctx: PipelineContext) -> None:
        """Evaluate all escalation reasons after L5 confirms a change.

        Writes ``escalate_to_ai`` and ``escalation_reasons`` to the
        pipeline context. Only active when ``ai_enabled`` is True.
        """
        if not self._deps.ai_enabled:
            return

        reasons: list[str] = []

        for signal in ctx.embedding_signals.values():
            if isinstance(signal, EmbeddingSignal) and signal.disagree:
                reasons.append(EscalationReason.SIGNAL_DISAGREEMENT.value)
                break

        if ctx.profile is not None:
            high_value_zones = getattr(ctx.profile, "high_value_zones", None)
            if high_value_zones:
                for zone_name in ctx.changed_zones:
                    if zone_name in high_value_zones:
                        reasons.append(EscalationReason.HIGH_VALUE_ZONE.value)
                        break

        in_gray = self._deps.ai_gray_band_low <= ctx.semantic_score < self._deps.ai_gray_band_high
        if in_gray:
            reasons.append(EscalationReason.GRAY_BAND.value)

        if EscalationReason.TEMPLATE_DRIFT.value not in reasons:
            pass

        if (
            ctx.profile is not None
            and getattr(ctx.profile, "always_enrich", False)
            and EscalationReason.FORCED.value not in reasons
        ):
            reasons.append(EscalationReason.FORCED.value)

        if reasons:
            ctx.escalate_to_ai = True
            ctx.escalation_reasons = reasons

    def _run_l2(self, ctx: PipelineContext) -> None:
        fingerprint = self._deps.fingerprint
        if fingerprint is None:
            return
        ctx.skeleton_hash = fingerprint.hash_skeleton(
            fingerprint.extract_skeleton(ctx.raw_html),
        )
        if self._deps.classifier is not None:
            cls_name = self._deps.classifier.classify(ctx.raw_html)
            if cls_name is not None:
                self._deps.classifier.zones_for_class(cls_name)

    def _run_l3(self, ctx: PipelineContext) -> None:
        extractor = self._deps.zone_extractor
        profile = ctx.profile
        if extractor is None or profile is None:
            return
        zone_texts = extractor.extract(
            ctx.raw_html,
            profile.zone_selectors,
        )
        ctx.current_zone_hashes = {
            name: hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
            for name, text in zone_texts.items()
        }
        changed_zones: dict[str, str] = {}
        for name, current_hash in ctx.current_zone_hashes.items():
            previous_hash = ctx.stored.zone_hashes.get(name, "")
            if current_hash != previous_hash:
                changed_zones[name] = current_hash
        if changed_zones:
            has_signal = False
            for name in list(changed_zones.keys()):
                zone = profile.get_zone(name)
                if zone is not None and zone.is_noise:
                    del changed_zones[name]
                else:
                    has_signal = True
            if not has_signal:
                changed_zones.clear()
        ctx.changed_zones = changed_zones
        ctx.stored.zone_hashes = dict(ctx.current_zone_hashes)

    async def _run_l4(self, ctx: PipelineContext) -> None:
        scorer = self._deps.scorer
        extractor = self._deps.zone_extractor
        embedding_scorer = self._deps.embedding_scorer
        profile = ctx.profile
        if scorer is None or extractor is None or profile is None:
            ctx.semantic_score = 0.0
            return
        zone_texts = extractor.extract(
            ctx.raw_html,
            profile.zone_selectors,
        )
        total_score = 0.0
        max_weight_sum = 0.01
        scored_zone_texts: dict[str, ZoneTextDelta] = {}
        embedding_signals: dict[str, EmbeddingSignal] = {}
        for zone_sel in profile.zone_selectors:
            if zone_sel.is_noise or zone_sel.weight <= 0.0:
                continue
            current = zone_texts.get(zone_sel.name, "")
            previous = ctx.stored.zone_texts.get(zone_sel.name, "")
            lexical_distance = scorer.score(previous, current)
            weighted = lexical_distance * zone_sel.weight
            total_score += weighted
            max_weight_sum += zone_sel.weight
            scored_zone_texts[zone_sel.name] = ZoneTextDelta(
                zone_name=zone_sel.name,
                previous_text=previous,
                current_text=current,
                zone_score=weighted,
            )
            if self._deps.ai_enabled and embedding_scorer is not None and previous != current:
                semantic_distance = await embedding_scorer.semantic_distance(
                    previous,
                    current,
                )
                disagree = abs(lexical_distance - semantic_distance) >= self._deps.ai_signal_disagree_delta
                signal = EmbeddingSignal(
                    lexical=lexical_distance,
                    semantic=semantic_distance,
                    disagree=disagree,
                )
                embedding_signals[zone_sel.name] = signal
                if semantic_distance < lexical_distance * 0.5:
                    total_score -= weighted * (1.0 - self._deps.ai_reword_damping)
                    total_score += weighted * self._deps.ai_reword_damping
                elif semantic_distance > lexical_distance * 2.0:
                    floor_contribution = self._deps.ai_semantic_floor * zone_sel.weight
                    if weighted < floor_contribution:
                        total_score += floor_contribution - weighted
        ctx.semantic_score = total_score / max_weight_sum if max_weight_sum > 0 else 0.0
        ctx.scored_zone_texts = scored_zone_texts
        ctx.embedding_signals = embedding_signals


def _skip(ctx: PipelineContext, reason: str) -> Any:
    ctx.result = PipelineResult.SKIP
    ctx.skip_reason = reason
    return ctx


def _change_detected(ctx: PipelineContext) -> Any:
    ctx.result = PipelineResult.CHANGE_DETECTED
    return ctx


class ProcessCrawlTaskUseCase(UseCase[dict[str, Any], Any]):
    """Run the L0/L1/L5 pipeline for a single crawl task.

    Steps:
        1. Check idempotency on task_id; drop replay.
        2. Check per-domain throttle; requeue with delay if blocked.
        3. Acquire a per-URL lease; if not acquired, no-op (duplicate).
        4. Load the URL; transition Idle -> Enqueued -> Crawling.
        5. Fetch, normalize, hash, diff (if changed).
        6. Persist snapshot + change + outbox row in one transaction.
        7. Reschedule; release the lease.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        crawler: Any,
        normalizer: HtmlNormalizerPort,
        differ: DifferPort,
        blob: BlobStoragePort,
        lock: LockPort,
        lease_ttl_seconds: int = 120,
        worker_id: str = "crawler",
        embedding_scorer: Any = None,
        ai_enabled: bool = False,
        ai_signal_disagree_delta: float = 0.35,
        ai_reword_damping: float = 0.5,
        ai_semantic_floor: float = 0.10,
        ai_gray_band_low: float = 0.03,
        ai_gray_band_high: float = 0.08,
        throttle: ThrottlePort | None = None,
        idempotency: IdempotencyPort | None = None,
        dlq: DeadLetterRepositoryPort | None = None,
        max_attempts: int = 3,
        retry_base_seconds: float = 5.0,
    ) -> None:
        super().__init__(uow_factory)
        self._crawler = crawler
        self._normalizer = normalizer
        self._differ = differ
        self._blob = blob
        self._lock = lock
        self._lease_ttl = lease_ttl_seconds
        self._worker_id = worker_id
        self._throttle = throttle
        self._idempotency = idempotency
        self._dlq = dlq
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._pipeline = _CrawlPipeline(
            _PipelineDeps(
                crawler=crawler,
                normalizer=normalizer,
                differ=differ,
                blob=blob,
                lock=lock,
                evaluator=ChangeSignificanceEvaluator(),
                embedding_scorer=embedding_scorer,
                ai_enabled=ai_enabled,
                ai_signal_disagree_delta=ai_signal_disagree_delta,
                ai_reword_damping=ai_reword_damping,
                ai_semantic_floor=ai_semantic_floor,
                ai_gray_band_low=ai_gray_band_low,
                ai_gray_band_high=ai_gray_band_high,
            ),
        )

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> Any:
        url_id: UUID = params["url_id"]
        task_id: str | None = params.get("task_id")
        attempt: int = params.get("attempt", 1)

        if task_id is not None and self._idempotency is not None:
            if await self._idempotency.is_seen(task_id):
                return {"status": "skipped_duplicate"}
            await self._idempotency.mark_seen(task_id)

        url = await uow.urls.get(url_id)
        if url is None:
            return {"status": "missing"}

        if self._throttle is not None:
            host = _extract_host(url.address.value)
            blocked = await self._throttle.acquire(host)
            if not blocked:
                return {"status": "throttled", "host": host}

        token = f"{self._worker_id}-{url_id}"
        lock_key = f"lens:lock:url:{url_id}"
        acquired = await self._lock.acquire(
            lock_key,
            ttl_seconds=self._lease_ttl,
            token=token,
        )
        if not acquired:
            return {"status": "skipped_locked"}
        try:
            now = uow.now()
            try:
                url.claim(
                    worker_id=self._worker_id,
                    lease_ttl=timedelta(seconds=self._lease_ttl),
                    now=now,
                )
            except Exception:
                return {"status": "not_idle"}
            await uow.urls.update(url)
            await uow.flush()
            return await self._run_pipeline(uow, url)
        except Exception as exc:
            if attempt >= self._max_attempts and self._dlq is not None:
                await self._dlq.add(
                    queue="crawl.tasks.dlq",
                    message_id=task_id or str(url_id),
                    body=params,
                    error=str(exc),
                )
                return {"status": "sent_to_dlq", "error": str(exc)}
            return {"status": "error", "error": str(exc), "attempt": attempt}
        finally:
            await self._lock.release(lock_key, token)

    async def _run_pipeline(self, uow: UnitOfWork, url: Url) -> dict[str, Any]:
        crawl_config, diff_config = self._resolve_configs(uow, url)
        try:
            raw: RawFetchResult = await self._crawler.fetch(
                url.address.value,
                crawl_config,
            )
        except Exception as exc:
            return await self._record_error(uow, url, str(exc))
        if not raw.is_success:
            return await self._record_error(
                uow,
                url,
                raw.error or f"http {raw.http_status}",
            )
        now = uow.now()
        try:
            url.start_crawl(now=now)
        except Exception as exc:
            url.release(now=now)
            await uow.urls.update(url)
            return {"status": "not_enqueued", "error": str(exc)}
        await uow.urls.update(url)
        await uow.flush()

        ctx = await self._build_context(uow, url, raw, crawl_config, diff_config)
        await self._pipeline.process(ctx)
        if ctx.result == PipelineResult.SKIP:
            return await self._record_skip(uow, url, ctx)
        return await self._record_change(uow, url, ctx)

    def _resolve_configs(self, uow: UnitOfWork, url: Url) -> tuple[CrawlConfig, DiffConfig]:
        if url.crawl_config is not None and url.diff_config is not None:
            return url.crawl_config, url.diff_config
        return (
            url.crawl_config or CrawlConfig(),
            url.diff_config or DiffConfig(),
        )

    async def _build_context(
        self,
        uow: UnitOfWork,
        url: Url,
        raw: RawFetchResult,
        crawl_config: CrawlConfig,
        diff_config: DiffConfig,
    ) -> PipelineContext:
        stored = await uow.url_check_states.get_for_url(url.id) or StoredCheckState(
            url_id=url.id,
            last_check_at=url.last_checked_at,
        )
        return PipelineContext(
            url_id=url.id,
            address=url.address.value,
            crawl_config=crawl_config,
            diff_config=diff_config,
            raw_html=raw.html,
            raw_bytes=raw.html.encode("utf-8"),
            http_status=raw.http_status,
            http_headers=dict(raw.headers),
            stored=stored,
        )

    async def _record_skip(self, uow: UnitOfWork, url: Url, ctx: PipelineContext) -> dict[str, Any]:
        from lens_domain.enums import UrlStatus

        now = uow.now()
        url.last_checked_at = now
        url.next_due_at = now + timedelta(seconds=url.interval.seconds)
        url.status = UrlStatus.IDLE
        url.consecutive_errors = 0
        url.locked_by = None
        url.lock_expires_at = None
        url.enqueued_at = None
        url.updated_at = now
        await uow.urls.update(url)
        if ctx.raw_md5 and ctx.filter_config_hash:
            await uow.url_check_states.upsert(
                StoredCheckState(
                    url_id=url.id,
                    raw_md5=ctx.raw_md5,
                    filter_config_hash=ctx.filter_config_hash,
                    last_etag=ctx.http_headers.get("etag") or ctx.stored.last_etag,
                    last_modified=ctx.http_headers.get("last-modified") or ctx.stored.last_modified,
                    zone_hashes=dict(ctx.current_zone_hashes or ctx.stored.zone_hashes),
                    zone_texts=dict(ctx.stored.zone_texts),
                    previous_cleaned_text=ctx.stored.previous_cleaned_text,
                    last_check_at=now,
                    profile_id=ctx.stored.profile_id,
                ),
            )
        await uow.flush()
        return {"status": "skipped", "reason": ctx.skip_reason}

    async def _record_change(self, uow: UnitOfWork, url: Url, ctx: PipelineContext) -> dict[str, Any]:
        now = uow.now()
        raw_bytes = ctx.raw_bytes
        # The content hash is computed on the normalized text (07 L1) so a
        # identical hash means the cleaned content is byte-for-byte equal.
        normalized_bytes = ctx.cleaned_text.encode("utf-8")
        content_hash = ContentHash(
            hex=hashlib.sha256(normalized_bytes).hexdigest(),
        )
        # Resolve the previous snapshot BEFORE adding the new one. The
        # in-memory fake would otherwise return the snapshot we just added.
        previous = await uow.snapshots.latest_for_url(url.id)
        if previous is not None and previous.content_hash == content_hash:
            ctx.skip_reason = "raw_hash_unchanged"
            return await self._record_skip(uow, url, ctx)
        previous_snapshot_id = previous.id_vo if previous is not None else None
        previous_text = ctx.stored.previous_cleaned_text
        snapshot_id = uow.new_id()
        blob_key = f"snapshots/{url.id}/{snapshot_id}.html.gz"
        await self._blob.put(blob_key, raw_bytes)
        snapshot = Snapshot.create(
            id=SnapshotId(snapshot_id),
            url_id=url.id_vo,
            content_ref=blob_key,
            content_hash=content_hash,
            http_status=ctx.http_status,
            byte_size=len(raw_bytes),
            fetched_at=now,
            now=now,
        )
        await uow.snapshots.add(snapshot)
        diff_result = await self._differ.diff(
            previous_text,
            ctx.cleaned_text,
            ctx.diff_config,
            UUID(int=0),
            self._blob,
        )
        change_id = uow.new_id()
        change = Change.build(
            id=ChangeId(change_id),
            url_id=url.id_vo,
            previous_hash=(previous.content_hash if previous is not None else None),
            new_hash=content_hash,
            previous_snapshot_id=previous_snapshot_id,
            new_snapshot_id=SnapshotId(snapshot_id),
            diff_summary=diff_result.summary,
            diff_ref=diff_result.diff_ref,
            semantic_score=ctx.semantic_score,
            significant=True,
            now=now,
        )
        await uow.changes.add(change)
        event = url.record_success(
            snapshot=snapshot,
            change=change,
            now=now,
        )
        await uow.urls.update(url)
        await uow.url_check_states.upsert(
            StoredCheckState(
                url_id=url.id,
                raw_md5=ctx.raw_md5,
                filter_config_hash=ctx.filter_config_hash,
                last_etag=ctx.http_headers.get("etag") or ctx.stored.last_etag,
                last_modified=ctx.http_headers.get("last-modified") or ctx.stored.last_modified,
                zone_hashes=dict(ctx.current_zone_hashes or ctx.stored.zone_hashes),
                zone_texts=dict(ctx.stored.zone_texts),
                previous_cleaned_text=ctx.cleaned_text,
                last_check_at=now,
                profile_id=ctx.stored.profile_id,
            ),
        )
        await uow.flush()
        if event is not None:
            event_id = uow.new_id()
            await uow.outbox.add(
                id=event_id,
                aggregate_type="url",
                aggregate_id=url.id,
                event_type=event.__class__.__name__,
                event_id=event.event_id,
                payload={
                    "url_id": str(event.url_id),
                    "change_id": str(event.change_id),
                    "domain_id": str(event.domain_id),
                    "category_id": (str(event.category_id) if event.category_id is not None else None),
                    "significant": event.significant,
                },
                created_at=now,
            )
            await uow.flush()
        if ctx.escalate_to_ai:
            enrich_event = ChangeNeedsEnrichment(
                event_id=UUID(int=0),
                occurred_at=now,
                url_id=url.id,
                change_id=change.id,
                domain_id=url.domain_id.value,
                category_id=url.category_id.value if url.category_id else None,
                template_class=(ctx.profile.template_class if ctx.profile is not None else None),
                escalation_reasons=tuple(ctx.escalation_reasons),
                changed_zones=tuple(
                    {"zone_name": z.zone_name, "zone_score": str(z.zone_score)}
                    for z in ctx.scored_zone_texts.values()
                    if z.current_text != z.previous_text
                ),
            )
            enrich_id = uow.new_id()
            await uow.outbox.add(
                id=enrich_id,
                aggregate_type="change",
                aggregate_id=change.id,
                event_type=enrich_event.__class__.__name__,
                event_id=enrich_id,
                payload={
                    "url_id": str(enrich_event.url_id),
                    "change_id": str(enrich_event.change_id),
                    "domain_id": str(enrich_event.domain_id),
                    "category_id": (str(enrich_event.category_id) if enrich_event.category_id is not None else None),
                    "template_class": enrich_event.template_class,
                    "escalation_reasons": list(enrich_event.escalation_reasons),
                    "changed_zones": [
                        {
                            "zone_name": z["zone_name"],
                            "zone_score": str(z["zone_score"]),
                        }
                        for z in enrich_event.changed_zones
                    ],
                },
                created_at=now,
            )
            await uow.flush()
        return {
            "status": "change_detected",
            "change_id": str(change.id),
            "snapshot_id": str(snapshot.id),
        }

    async def _record_error(self, uow: UnitOfWork, url: Url, error: str) -> dict[str, Any]:
        now = uow.now()
        event_id = uow.new_id()
        event = url.record_error(error, event_id=event_id, now=now)
        await uow.urls.update(url)
        await uow.flush()
        await uow.outbox.add(
            id=event_id,
            aggregate_type="url",
            aggregate_id=url.id,
            event_type=event.__class__.__name__,
            event_id=event.event_id,
            payload={
                "url_id": str(event.url_id),
                "domain_id": str(event.domain_id),
                "category_id": (str(event.category_id) if event.category_id is not None else None),
                "error": event.error,
                "consecutive_errors": event.consecutive_errors,
            },
            created_at=now,
        )
        await uow.flush()
        return {
            "status": "error",
            "error": error,
            "consecutive_errors": url.consecutive_errors,
        }


# ---------------------------------------------------------------------------
# History / diff / snapshot queries
# ---------------------------------------------------------------------------


class ListChangesUseCase(UseCase[dict[str, Any], ListResult[ChangeDto]]):
    """List changes for a URL, optionally filtered by ``since``."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ListResult[ChangeDto]:
        url_id: UUID = params["url_id"]
        since: datetime | None = params.get("since")
        limit: int = params.get("limit", 50)
        items = await uow.changes.list_for_url(
            url_id,
            since=since,
            limit=limit,
        )
        return ListResult[ChangeDto](
            items=[change_to_dto(c) for c in items],
            next_cursor=None,
        )


class GetChangeUseCase(UseCase[UUID, ChangeDto]):
    """Return a single persisted :class:`Change` as a :class:`ChangeDto`."""

    async def run(self, change_id: UUID, uow: UnitOfWork) -> ChangeDto:
        change = await uow.changes.get(change_id)
        if change is None:
            raise NotFoundError(f"change not found: {change_id!s}")
        return change_to_dto(change)


class GetChangeDiffUseCase(UseCase[UUID, dict[str, Any]]):
    """Return the stored diff metadata for a change.

    The full unified diff is read separately via
    :class:`GetChangeDiffBlobUseCase`; this use case only reports the
    blob reference and the line-count summary.
    """

    async def run(self, change_id: UUID, uow: UnitOfWork) -> dict[str, Any]:
        change = await uow.changes.get(change_id)
        if change is None:
            raise NotFoundError(f"change not found: {change_id!s}")
        return {
            "id": change.id,
            "url_id": change.url_id.value,
            "diff_ref": change.diff_ref,
            "summary": {
                "added_count": change.diff_summary.added_count,
                "removed_count": change.diff_summary.removed_count,
            },
        }


class GetChangeDiffBlobUseCase:
    """Read the unified-diff blob for a change.

    Returns the decoded text (gzip already handled by the blob store).
    Use case is intentionally *not* a :class:`UseCase` because it depends
    on an injected :class:`BlobStoragePort` rather than the UoW.
    """

    def __init__(self, blob_storage: BlobStoragePort) -> None:
        self._blob = blob_storage

    async def execute(self, change_id: UUID, uow: UnitOfWork) -> str | None:
        change = await uow.changes.get(change_id)
        if change is None:
            raise NotFoundError(f"change not found: {change_id!s}")
        if change.diff_ref is None:
            return None
        data = await self._blob.get(change.diff_ref)
        return data.decode("utf-8")


class GetLatestSnapshotUseCase(UseCase[UUID, SnapshotDto]):
    """Return the latest snapshot for a URL."""

    async def run(self, url_id: UUID, uow: UnitOfWork) -> SnapshotDto:
        snap = await uow.snapshots.latest_for_url(url_id)
        if snap is None:
            raise NotFoundError(f"no snapshot for url {url_id!s}")
        return snapshot_to_dto(snap)


class GetSnapshotUseCase(UseCase[UUID, SnapshotDto]):
    """Return a single snapshot by its id."""

    async def run(self, snapshot_id: UUID, uow: UnitOfWork) -> SnapshotDto:
        snap = await uow.snapshots.get(snapshot_id)
        if snap is None:
            raise NotFoundError(f"snapshot not found: {snapshot_id!s}")
        return snapshot_to_dto(snap)


class ListSnapshotsUseCase(UseCase[UUID, list[SnapshotDto]]):
    """List snapshots for a URL, most recent first."""

    async def run(self, url_id: UUID, uow: UnitOfWork) -> list[SnapshotDto]:
        items = await uow.snapshots.list_for_url(url_id, limit=200)
        return [snapshot_to_dto(snap) for snap in items]
