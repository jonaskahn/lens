"""Domain entities with encapsulated invariants.

Entities are mutable in the sense that their state changes through business
operations (``record_success``, ``mark_due``, etc.); each operation enforces
its invariants and may emit a domain event. The base class
:class:`_Entity` provides identity-based equality and hashing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, ClassVar
from uuid import UUID

from lens_common.errors import DomainError
from lens_domain.enums import BindingScope, ChannelKind, UrlStatus
from lens_domain.errors import (
    DuplicateCategory,
    HostMismatch,
    InvalidScope,
    InvalidStateTransition,
)
from lens_domain.events import UrlChangeDetected, UrlCrawlFailed
from lens_domain.ids import CategoryId, ChangeId, DomainId, ProfileId, SnapshotId, UrlId
from lens_domain.value_objects import (
    Address,
    ContentHash,
    CrawlConfig,
    DiffConfig,
    DiffSummary,
    Hostname,
    Interval,
    NotificationRouting,
    Politeness,
    SignificanceRule,
    ZoneSelector,
)

__all__ = [
    "Category",
    "Change",
    "Channel",
    "ChannelBinding",
    "Domain",
    "SiteProfile",
    "Snapshot",
    "Url",
]


class _Entity:
    """Marker base for identity-based equality."""

    __slots__ = ("_id",)

    def __init__(self, id: UUID) -> None:
        self._id = id

    @property
    def id(self) -> UUID:
        return self._id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Entity) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id!s})"


class Domain(_Entity):
    """A tracked website domain (aggregate root).

    Holds host, display name, defaults that child entities inherit, and the
    politeness policy applied when crawling the host. Invariant: ``host`` is
    a valid normalised :class:`Hostname`.
    """

    DEFAULT_CRAWL: ClassVar[CrawlConfig] = CrawlConfig()
    DEFAULT_DIFF: ClassVar[DiffConfig] = DiffConfig()
    DEFAULT_POLITENESS: ClassVar[Politeness] = Politeness()
    DEFAULT_ROUTING: ClassVar[NotificationRouting] = NotificationRouting()

    def __init__(
        self,
        id: DomainId,
        host: Hostname,
        *,
        display_name: str | None = None,
        enabled: bool = True,
        default_crawl_config: CrawlConfig | None = None,
        default_diff_config: DiffConfig | None = None,
        politeness: Politeness | None = None,
        default_routing: NotificationRouting | None = None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id.value)
        self._id_vo = id
        self.host = host
        self.display_name = display_name
        self.enabled = enabled
        self.default_crawl_config = default_crawl_config or self.DEFAULT_CRAWL
        self.default_diff_config = default_diff_config or self.DEFAULT_DIFF
        self.politeness = politeness or self.DEFAULT_POLITENESS
        self.default_routing = default_routing or self.DEFAULT_ROUTING
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def id_vo(self) -> DomainId:
        return self._id_vo

    @classmethod
    def create(
        cls,
        id: DomainId,
        host: str,
        *,
        display_name: str | None = None,
        enabled: bool = True,
        default_crawl_config: CrawlConfig | None = None,
        default_diff_config: DiffConfig | None = None,
        politeness: Politeness | None = None,
        default_routing: NotificationRouting | None = None,
        now: datetime,
    ) -> Domain:
        """Build a new :class:`Domain` with default timestamps."""
        return cls(
            id=id,
            host=Hostname(value=host),
            display_name=display_name,
            enabled=enabled,
            default_crawl_config=default_crawl_config,
            default_diff_config=default_diff_config,
            politeness=politeness,
            default_routing=default_routing,
            created_at=now,
            updated_at=now,
        )

    def change_host(self, new_host: str, *, now: datetime) -> None:
        """Change the host, validating it normalises to a valid hostname."""
        self.host = Hostname(value=new_host)
        self.updated_at = now

    def update(
        self,
        *,
        display_name: str | None = None,
        enabled: bool | None = None,
        default_crawl_config: CrawlConfig | None = None,
        default_diff_config: DiffConfig | None = None,
        politeness: Politeness | None = None,
        default_routing: NotificationRouting | None = None,
        now: datetime,
    ) -> None:
        """Replace mutable fields in one call; ``None`` means leave unchanged."""
        if display_name is not None:
            self.display_name = display_name
        if enabled is not None:
            self.enabled = enabled
        if default_crawl_config is not None:
            self.default_crawl_config = default_crawl_config
        if default_diff_config is not None:
            self.default_diff_config = default_diff_config
        if politeness is not None:
            self.politeness = politeness
        if default_routing is not None:
            self.default_routing = default_routing
        self.updated_at = now


class Category(_Entity):
    """A category that groups URLs within a :class:`Domain`."""

    def __init__(
        self,
        id: CategoryId,
        domain_id: DomainId,
        name: str,
        *,
        description: str | None = None,
        crawl_config: CrawlConfig | None = None,
        diff_config: DiffConfig | None = None,
        routing: NotificationRouting | None = None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id.value)
        self._id_vo = id
        self.domain_id = domain_id
        self.name = name.strip()
        if not self.name:
            raise DuplicateCategory("category name must not be empty")
        self.description = description
        self.crawl_config = crawl_config
        self.diff_config = diff_config
        self.routing = routing
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def id_vo(self) -> CategoryId:
        return self._id_vo

    @classmethod
    def create(
        cls,
        id: CategoryId,
        domain_id: DomainId,
        name: str,
        *,
        description: str | None = None,
        crawl_config: CrawlConfig | None = None,
        diff_config: DiffConfig | None = None,
        routing: NotificationRouting | None = None,
        now: datetime,
    ) -> Category:
        return cls(
            id=id,
            domain_id=domain_id,
            name=name,
            description=description,
            crawl_config=crawl_config,
            diff_config=diff_config,
            routing=routing,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        crawl_config: CrawlConfig | None = None,
        diff_config: DiffConfig | None = None,
        routing: NotificationRouting | None = None,
        now: datetime,
    ) -> None:
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise DuplicateCategory("category name must not be empty")
            self.name = new_name
        if description is not None:
            self.description = description
        if crawl_config is not None:
            self.crawl_config = crawl_config
        if diff_config is not None:
            self.diff_config = diff_config
        if routing is not None:
            self.routing = routing
        self.updated_at = now


class Url(_Entity):
    """A tracked URL (aggregate root for crawling)."""

    def __init__(
        self,
        id: UrlId,
        domain_id: DomainId,
        address: Address,
        interval: Interval,
        *,
        category_id: CategoryId | None = None,
        enabled: bool = True,
        crawl_config: CrawlConfig | None = None,
        diff_config: DiffConfig | None = None,
        routing: NotificationRouting | None = None,
        status: UrlStatus = UrlStatus.IDLE,
        last_checked_at: datetime | None = None,
        next_due_at: datetime,
        last_hash: str | None = None,
        consecutive_errors: int = 0,
        locked_by: str | None = None,
        lock_expires_at: datetime | None = None,
        enqueued_at: datetime | None = None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id.value)
        self._id_vo = id
        self.domain_id = domain_id
        self.address = address
        self.category_id = category_id
        self.enabled = enabled
        self.crawl_config = crawl_config
        self.diff_config = diff_config
        self.routing = routing
        self.interval = interval
        self.status = status
        self.last_checked_at = last_checked_at
        self.next_due_at = next_due_at
        self.last_hash = last_hash
        self.consecutive_errors = consecutive_errors
        self.locked_by = locked_by
        self.lock_expires_at = lock_expires_at
        self.enqueued_at = enqueued_at
        self.created_at = created_at
        self.updated_at = updated_at
        if self.consecutive_errors < 0:
            raise DomainError("consecutive_errors must be >= 0")

    @property
    def id_vo(self) -> UrlId:
        return self._id_vo

    @classmethod
    def create(
        cls,
        id: UrlId,
        domain_id: DomainId,
        address: str,
        interval_seconds: int,
        *,
        domain_host: Hostname,
        category_id: CategoryId | None = None,
        enabled: bool = True,
        crawl_config: CrawlConfig | None = None,
        diff_config: DiffConfig | None = None,
        routing: NotificationRouting | None = None,
        global_min_interval: int = 300,
        now: datetime,
    ) -> Url:
        """Build a new :class:`Url`, enforcing host match + interval floor.

        Raises:
            HostMismatch: when the address host does not match ``domain_host``.
            InvalidAddress: when ``address`` is not a valid absolute URL.
            InvalidInterval: when ``interval_seconds`` is below the floor.
        """
        parsed = Address(value=address)
        if parsed.host != domain_host.value:
            raise HostMismatch(
                f"url host {parsed.host!r} does not match domain {domain_host.value!r}",
            )
        interval = Interval(
            seconds=interval_seconds,
            global_minimum=global_min_interval,
        )
        return cls(
            id=id,
            domain_id=domain_id,
            address=parsed,
            interval=interval,
            category_id=category_id,
            enabled=enabled,
            crawl_config=crawl_config,
            diff_config=diff_config,
            routing=routing,
            next_due_at=now,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        enabled: bool | None = None,
        interval_seconds: int | None = None,
        crawl_config: CrawlConfig | None = None,
        diff_config: DiffConfig | None = None,
        routing: NotificationRouting | None = None,
        global_min_interval: int = 300,
        now: datetime,
    ) -> None:
        if enabled is not None:
            self.enabled = enabled
        if interval_seconds is not None:
            self.interval = Interval(
                seconds=interval_seconds,
                global_minimum=global_min_interval,
            )
        if crawl_config is not None:
            self.crawl_config = crawl_config
        if diff_config is not None:
            self.diff_config = diff_config
        if routing is not None:
            self.routing = routing
        self.updated_at = now

    def is_lease_held(self, by: str, now: datetime) -> bool:
        """True if ``by`` currently holds the URL lease."""
        return self.locked_by == by and (self.lock_expires_at is not None and self.lock_expires_at > now)

    def lease_is_expired(self, now: datetime) -> bool:
        """True if a lease exists but has expired."""
        return self.locked_by is not None and self.lock_expires_at is not None and self.lock_expires_at <= now

    def mark_due(self, *, now: datetime) -> None:
        """Reset to ``Idle`` and schedule a re-check now (used for check-now)."""
        self.status = UrlStatus.IDLE
        self.next_due_at = now
        self.updated_at = now

    def claim(self, worker_id: str, lease_ttl: timedelta, *, now: datetime) -> None:
        """Acquire the URL lease and move to ``Enqueued``.

        Raises:
            InvalidStateTransition: if the URL is not currently ``Idle``.
        """
        if self.status != UrlStatus.IDLE:
            raise InvalidStateTransition(
                f"cannot claim url from status {self.status.value!r}",
            )
        self.status = UrlStatus.ENQUEUED
        self.locked_by = worker_id
        self.lock_expires_at = now + lease_ttl
        self.enqueued_at = now
        self.updated_at = now

    def start_crawl(self, *, now: datetime) -> None:
        """Transition from ``Enqueued`` to ``Crawling``.

        Raises:
            InvalidStateTransition: if the URL is not currently ``Enqueued``.
        """
        if self.status != UrlStatus.ENQUEUED:
            raise InvalidStateTransition(
                f"cannot start crawl from status {self.status.value!r}",
            )
        self.status = UrlStatus.CRAWLING
        self.updated_at = now

    def record_success(
        self,
        *,
        snapshot: Snapshot,
        change: Change | None,
        now: datetime,
    ) -> UrlChangeDetected | None:
        """Persist a successful crawl; reschedule the URL; return the change event.

        ``change`` is ``None`` for unchanged content (no event emitted). The URL
        transitions back to ``Idle`` and the next due time advances by the
        configured interval. The lease is released here.
        """
        if self.status != UrlStatus.CRAWLING:
            raise InvalidStateTransition(
                f"cannot record success from status {self.status.value!r}",
            )
        self.status = UrlStatus.IDLE
        self.last_checked_at = snapshot.fetched_at
        self.last_hash = snapshot.content_hash.hex
        self.consecutive_errors = 0
        self.next_due_at = now + timedelta(seconds=self.interval.seconds)
        self.locked_by = None
        self.lock_expires_at = None
        self.enqueued_at = None
        self.updated_at = now
        if change is None:
            return None
        return UrlChangeDetected(
            event_id=change.id,
            occurred_at=now,
            url_id=self.id,
            change_id=change.id,
            domain_id=self.domain_id.value,
            category_id=self.category_id.value if self.category_id else None,
            significant=change.significant,
        )

    def record_error(
        self,
        error: str,
        *,
        event_id: UUID,
        now: datetime,
    ) -> UrlCrawlFailed:
        """Record a crawl failure, increment errors, schedule a backoff, release.

        Emits a :class:`UrlCrawlFailed` event the caller can persist, carrying
        the supplied ``event_id`` so the outbox / notifier can deduplicate on a
        unique message identity. The URL returns to ``Idle`` so the scheduler
        picks it up again after the backoff.
        """
        self.consecutive_errors += 1
        self.status = UrlStatus.IDLE
        backoff = self._backoff_seconds()
        self.next_due_at = now + timedelta(seconds=backoff)
        self.last_checked_at = now
        self.locked_by = None
        self.lock_expires_at = None
        self.enqueued_at = None
        self.updated_at = now
        return UrlCrawlFailed(
            event_id=event_id,
            occurred_at=now,
            url_id=self.id,
            domain_id=self.domain_id.value,
            category_id=self.category_id.value if self.category_id else None,
            error=error,
            consecutive_errors=self.consecutive_errors,
        )

    def release(self, *, now: datetime) -> None:
        """Release the lease and return the URL to ``Idle`` (no progress made)."""
        self.locked_by = None
        self.lock_expires_at = None
        self.enqueued_at = None
        if self.status in {UrlStatus.ENQUEUED, UrlStatus.CRAWLING}:
            self.status = UrlStatus.IDLE
        self.updated_at = now

    def disable_due_to_errors(self, *, now: datetime) -> None:
        """Move the URL to ``Disabled`` after too many consecutive errors."""
        self.status = UrlStatus.DISABLED
        self.locked_by = None
        self.lock_expires_at = None
        self.updated_at = now

    def _backoff_seconds(self) -> int:
        """Return the next-reschedule delay using exponential backoff (capped)."""
        base: int = max(self.interval.seconds, 60)
        cap: int = base * 64
        delay: int = base * (2 ** min(self.consecutive_errors, 6))
        return int(min(delay, cap))


class Channel(_Entity):
    """A delivery channel (Apprise URL-backed notification target)."""

    def __init__(
        self,
        id: UUID,
        name: str,
        kind: ChannelKind,
        apprise_url: str,
        *,
        enabled: bool = True,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id)
        if not name.strip():
            raise DomainError("channel name must not be empty")
        if not apprise_url.strip():
            raise DomainError("channel apprise_url must not be empty")
        self.name = name.strip()
        self.kind = kind
        self.apprise_url = apprise_url
        self.enabled = enabled
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def create(
        cls,
        id: UUID,
        name: str,
        kind: ChannelKind,
        apprise_url: str,
        *,
        enabled: bool = True,
        now: datetime,
    ) -> Channel:
        return cls(
            id=id,
            name=name,
            kind=kind,
            apprise_url=apprise_url,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        kind: ChannelKind | None = None,
        apprise_url: str | None = None,
        enabled: bool | None = None,
        now: datetime,
    ) -> None:
        if name is not None:
            stripped = name.strip()
            if not stripped:
                raise DomainError("channel name must not be empty")
            self.name = stripped
        if kind is not None:
            self.kind = kind
        if apprise_url is not None:
            stripped_url = apprise_url.strip()
            if not stripped_url:
                raise DomainError("channel apprise_url must not be empty")
            self.apprise_url = stripped_url
        if enabled is not None:
            self.enabled = enabled
        self.updated_at = now


class ChannelBinding(_Entity):
    """A binding of a :class:`Channel` to a scope with trigger flags."""

    def __init__(
        self,
        id: UUID,
        channel_id: UUID,
        scope: BindingScope,
        *,
        scope_id: UUID | None = None,
        on_change: bool = True,
        on_error: bool = False,
        on_no_change: bool = False,
        created_at: datetime,
    ) -> None:
        super().__init__(id)
        self.channel_id = channel_id
        if scope == BindingScope.GLOBAL and scope_id is not None:
            raise InvalidScope("global bindings must not have a scope_id")
        if scope != BindingScope.GLOBAL and scope_id is None:
            raise InvalidScope(f"{scope.value} bindings require a scope_id")
        self.scope = scope
        self.scope_id = scope_id
        self.on_change = on_change
        self.on_error = on_error
        self.on_no_change = on_no_change
        self.created_at = created_at

    @classmethod
    def create(
        cls,
        id: UUID,
        channel_id: UUID,
        scope: BindingScope,
        *,
        scope_id: UUID | None = None,
        on_change: bool = True,
        on_error: bool = False,
        on_no_change: bool = False,
        now: datetime,
    ) -> ChannelBinding:
        return cls(
            id=id,
            channel_id=channel_id,
            scope=scope,
            scope_id=scope_id,
            on_change=on_change,
            on_error=on_error,
            on_no_change=on_no_change,
            created_at=now,
        )

    def update(
        self,
        *,
        on_change: bool | None = None,
        on_error: bool | None = None,
        on_no_change: bool | None = None,
    ) -> None:
        if on_change is not None:
            self.on_change = on_change
        if on_error is not None:
            self.on_error = on_error
        if on_no_change is not None:
            self.on_no_change = on_no_change


class SiteProfile(_Entity):
    """A per-domain URL-pattern profile that stores zone selectors and template metadata.

    Resolved during L2 of the content processing pipeline. When the DOM
    skeleton hash changes, a new version is created and a
    :class:`SiteTemplateDriftDetected` event may be emitted.
    """

    DEFAULT_THRESHOLD: float = 0.05
    DEFAULT_ZONE_SELECTORS: ClassVar[list[ZoneSelector]] = [
        ZoneSelector(
            name="navigation",
            css_selector="nav, header nav, [role='navigation'], .nav, #nav",
            weight=0.0,
            is_noise=True,
        ),
        ZoneSelector(
            name="main_content",
            css_selector="main, [role='main'], article, .main-content, #main, #content, .content",
            weight=1.0,
            is_noise=False,
        ),
        ZoneSelector(
            name="sidebar",
            css_selector="aside, [role='complementary'], .sidebar, #sidebar",
            weight=0.3,
            is_noise=False,
        ),
        ZoneSelector(
            name="price",
            css_selector="[itemprop='price'], [class*='price'], [class*='Price'], .price",
            weight=2.0,
            is_noise=False,
        ),
        ZoneSelector(
            name="availability",
            css_selector="[itemprop='availability'], [class*='stock'], [class*='availability'], .in-stock, .out-of-stock",
            weight=1.5,
            is_noise=False,
        ),
        ZoneSelector(
            name="footer",
            css_selector="footer, [role='contentinfo'], .footer, #footer",
            weight=0.0,
            is_noise=True,
        ),
    ]

    def __init__(
        self,
        id: ProfileId,
        domain: str,
        url_pattern: str,
        *,
        template_hash: str | None = None,
        template_class: str | None = None,
        zone_selectors: list[ZoneSelector] | None = None,
        significance_rules: list[SignificanceRule] | None = None,
        semantic_threshold: float = DEFAULT_THRESHOLD,
        version: int = 1,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__(id.value)
        self._id_vo = id
        if not domain:
            raise DomainError("site profile domain must not be empty")
        if not url_pattern:
            raise DomainError("site profile url_pattern must not be empty")
        self.domain = domain
        self.url_pattern = url_pattern
        self.template_hash = template_hash
        self.template_class = template_class
        self.zone_selectors = zone_selectors or list(self.DEFAULT_ZONE_SELECTORS)
        self.significance_rules = significance_rules or []
        self.semantic_threshold = semantic_threshold
        self.version = version
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def id_vo(self) -> ProfileId:
        return self._id_vo

    @classmethod
    def bootstrap(
        cls,
        id: ProfileId,
        domain: str,
        url_pattern: str,
        *,
        template_hash: str | None = None,
        template_class: str | None = None,
        zone_selectors: list[ZoneSelector] | None = None,
        semantic_threshold: float = DEFAULT_THRESHOLD,
        now: datetime,
    ) -> SiteProfile:
        return cls(
            id=id,
            domain=domain,
            url_pattern=url_pattern,
            template_hash=template_hash,
            template_class=template_class,
            zone_selectors=zone_selectors,
            semantic_threshold=semantic_threshold,
            version=1,
            created_at=now,
            updated_at=now,
        )

    def with_new_skeleton(self, new_hash: str, *, now: datetime) -> SiteProfile:
        """Return a copy with updated template_hash and version."""
        return SiteProfile(
            id=self._id_vo,
            domain=self.domain,
            url_pattern=self.url_pattern,
            template_hash=new_hash,
            template_class=self.template_class,
            zone_selectors=list(self.zone_selectors),
            significance_rules=list(self.significance_rules),
            semantic_threshold=self.semantic_threshold,
            version=self.version + 1,
            created_at=self.created_at,
            updated_at=now,
        )

    def get_zone(self, name: str) -> ZoneSelector | None:
        for selector in self.zone_selectors:
            if selector.name == name:
                return selector
        return None


class Snapshot(_Entity):
    """A persisted snapshot of a single crawled URL.

    Carries the identity (:class:`ContentHash`) computed on the normalized
    content together with the storage reference for the gzipped HTML blob.
    Factories enforce that the supplied content hash already matches the
    supplied content reference, so a snapshot row never references a hash
    that disagrees with what was actually stored.
    """

    def __init__(
        self,
        id: SnapshotId,
        url_id: UrlId,
        content_ref: str,
        content_hash: ContentHash,
        *,
        http_status: int | None = None,
        byte_size: int | None = None,
        fetched_at: datetime,
        created_at: datetime,
    ) -> None:
        super().__init__(id.value)
        self._id_vo = id
        self.url_id = url_id
        if not content_ref:
            raise DomainError("snapshot content_ref must not be empty")
        self.content_ref = content_ref
        self.content_hash = content_hash
        self.http_status = http_status
        self.byte_size = byte_size
        self.fetched_at = fetched_at
        self.created_at = created_at

    @property
    def id_vo(self) -> SnapshotId:
        return self._id_vo

    @classmethod
    def create(
        cls,
        id: SnapshotId,
        url_id: UrlId,
        content_ref: str,
        content_hash: ContentHash,
        *,
        http_status: int | None = None,
        byte_size: int | None = None,
        fetched_at: datetime,
        now: datetime,
    ) -> Snapshot:
        """Build a new :class:`Snapshot` with a creation timestamp from ``now``."""
        return cls(
            id=id,
            url_id=url_id,
            content_ref=content_ref,
            content_hash=content_hash,
            http_status=http_status,
            byte_size=byte_size,
            fetched_at=fetched_at,
            created_at=now,
        )


class Change(_Entity):
    """A change between two snapshots of the same URL.

    Factories require a hash mismatch with the previous snapshot, a
    non-negative diff summary, and at least one of the two snapshot
    references to be populated.
    """

    def __init__(
        self,
        id: ChangeId,
        url_id: UrlId,
        new_snapshot_id: SnapshotId,
        diff_summary: DiffSummary,
        *,
        previous_snapshot_id: SnapshotId | None = None,
        diff_ref: str | None = None,
        semantic_score: float | None = None,
        significant: bool = True,
        enrichment_status: str = "pending",
        created_at: datetime,
    ) -> None:
        super().__init__(id.value)
        self._id_vo = id
        self.url_id = url_id
        if not isinstance(diff_summary, DiffSummary):
            raise DomainError("change requires a DiffSummary value object")
        self.diff_summary = diff_summary
        self.previous_snapshot_id = previous_snapshot_id
        self.new_snapshot_id = new_snapshot_id
        self.diff_ref = diff_ref
        self.semantic_score = semantic_score
        self.significant = significant
        self.enrichment_status = enrichment_status
        self.created_at = created_at

    @property
    def id_vo(self) -> ChangeId:
        return self._id_vo

    @classmethod
    def create(
        cls,
        id: ChangeId,
        url_id: UrlId,
        new_snapshot_id: SnapshotId,
        diff_summary: DiffSummary,
        *,
        previous_snapshot_id: SnapshotId | None = None,
        diff_ref: str | None = None,
        semantic_score: float | None = None,
        significant: bool = True,
        now: datetime,
    ) -> Change:
        """Build a new :class:`Change` with a creation timestamp from ``now``."""
        return cls(
            id=id,
            url_id=url_id,
            new_snapshot_id=new_snapshot_id,
            previous_snapshot_id=previous_snapshot_id,
            diff_summary=diff_summary,
            diff_ref=diff_ref,
            semantic_score=semantic_score,
            significant=significant,
            created_at=now,
        )

    @classmethod
    def build(
        cls,
        *,
        id: ChangeId,
        url_id: UrlId,
        previous_hash: ContentHash | None,
        new_hash: ContentHash,
        previous_snapshot_id: SnapshotId | None,
        new_snapshot_id: SnapshotId,
        diff_summary: DiffSummary,
        diff_ref: str | None = None,
        semantic_score: float | None = None,
        significant: bool = True,
        now: datetime,
    ) -> Change:
        """Build a change when the hashes differ; raise when they match.

        This is the standard factory used by the application layer: a change
        only exists when the new content hash differs from the previous one.
        """
        if previous_hash is not None and previous_hash.hex == new_hash.hex:
            raise DomainError("change requires a hash mismatch with the previous snapshot")
        return cls.create(
            id=id,
            url_id=url_id,
            new_snapshot_id=new_snapshot_id,
            previous_snapshot_id=previous_snapshot_id,
            diff_summary=diff_summary,
            diff_ref=diff_ref,
            semantic_score=semantic_score,
            significant=significant,
            now=now,
        )


def to_dict(entity: _Entity) -> dict[str, Any]:
    """Serialise a known entity to a plain dict (best-effort).

    Use only for transport-shaped DTOs; this helper exists to keep tests
    concise and is not the persistence path (see :mod:`lens_infrastructure`).
    """
    from dataclasses import asdict, is_dataclass

    if is_dataclass(entity):
        return asdict(entity)
    return dict(entity.__dict__)
