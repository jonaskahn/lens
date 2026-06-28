"""Domain services: pure, no I/O.

The :class:`EffectiveConfigResolver` implements the URL > Category > Domain > Global
precedence rule for the effective :class:`CrawlConfig`, :class:`DiffConfig`, and
:class:`NotificationRouting` of a :class:`Url`. The merge is field-level: a field
set at a more specific level overrides; unset fields fall through.

The :class:`NotificationRouter` resolves the ordered, de-duplicated set of
notification :class:`Channel` targets for a domain event, honoring the same
precedence and the trigger flags carried by each :class:`ChannelBinding`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from lens_domain.entities import Category, Channel, ChannelBinding, Domain, Url
from lens_domain.enums import BindingScope, TriggerType
from lens_domain.value_objects import (
    CrawlConfig,
    DiffConfig,
    NotificationRouting,
    SignificanceRule,
)

__all__ = [
    "ChangeSignificanceEvaluator",
    "EffectiveConfigResolver",
    "GlobalDefaults",
    "NotificationRouter",
    "RouterRequest",
]


@dataclass(frozen=True, slots=True)
class GlobalDefaults:
    """Code- or env-level defaults that apply when nothing more specific does."""

    crawl: CrawlConfig
    diff: DiffConfig
    routing: NotificationRouting


class _UrlLike(Protocol):
    """Structural shape the resolver needs from a URL entity."""

    crawl_config: CrawlConfig | None
    diff_config: DiffConfig | None
    routing: NotificationRouting | None
    category_id: object | None
    domain_id: object


def _field_is_unset(model: Any, field_name: str) -> bool:
    """Return True if the model field is at its declared default (unset)."""
    field = type(model).model_fields[field_name]
    default: Any = field.default
    current: Any = getattr(model, field_name)
    if default is None:
        return current is None
    if isinstance(default, list | dict | set):
        return not bool(current)
    return bool(current == default)


def _apply_over(base: CrawlConfig, override: CrawlConfig) -> CrawlConfig:
    """Return a new CrawlConfig with ``override``'s set fields taking precedence."""
    payload: dict[str, Any] = {**base.model_dump()}
    for name in type(base).model_fields:
        if not _field_is_unset(override, name):
            payload[name] = getattr(override, name)
    return CrawlConfig(**payload)


def _apply_over_diff(base: DiffConfig, override: DiffConfig) -> DiffConfig:
    payload: dict[str, Any] = {**base.model_dump()}
    for name in type(base).model_fields:
        if not _field_is_unset(override, name):
            payload[name] = getattr(override, name)
    return DiffConfig(**payload)


def _apply_over_routing(
    base: NotificationRouting,
    override: NotificationRouting,
) -> NotificationRouting:
    channel_ids = list(override.channel_ids) if override.channel_ids else list(base.channel_ids)
    triggers = set(override.triggers) if override.triggers else set(base.triggers)
    return NotificationRouting(channel_ids=channel_ids, triggers=triggers)


def _merge_crawl(*candidates: CrawlConfig | None) -> CrawlConfig:
    """Field-level merge: URL > Category > Domain > Global; fall through if None."""
    result: CrawlConfig = CrawlConfig()
    for candidate in candidates:
        if candidate is None:
            continue
        result = _apply_over(result, candidate)
    return result


def _merge_diff(*candidates: DiffConfig | None) -> DiffConfig:
    result: DiffConfig = DiffConfig()
    for candidate in candidates:
        if candidate is None:
            continue
        result = _apply_over_diff(result, candidate)
    return result


def _merge_routing(*candidates: NotificationRouting | None) -> NotificationRouting:
    result: NotificationRouting = NotificationRouting()
    for candidate in candidates:
        if candidate is None:
            continue
        result = _apply_over_routing(result, candidate)
    return result


class EffectiveConfigResolver:
    """Resolve effective configuration by precedence: URL > Category > Domain > Global."""

    def __init__(self, globals_: GlobalDefaults) -> None:
        self._globals = globals_

    @property
    def defaults(self) -> GlobalDefaults:
        """Return the global defaults this resolver was constructed with."""
        return self._globals

    def resolve_crawl(
        self,
        url: _UrlLike | Url,
        category: Category | None,
        domain: Domain,
    ) -> CrawlConfig:
        """Return the effective crawl config for ``url``."""
        return _merge_crawl(
            self._globals.crawl,
            domain.default_crawl_config,
            category.crawl_config if category is not None else None,
            getattr(url, "crawl_config", None),
        )

    def resolve_diff(
        self,
        url: _UrlLike | Url,
        category: Category | None,
        domain: Domain,
    ) -> DiffConfig:
        """Return the effective diff config for ``url``."""
        return _merge_diff(
            self._globals.diff,
            domain.default_diff_config,
            category.diff_config if category is not None else None,
            getattr(url, "diff_config", None),
        )

    def resolve_routing(
        self,
        url: _UrlLike | Url,
        category: Category | None,
        domain: Domain,
    ) -> NotificationRouting:
        """Return the effective notification routing for ``url``."""
        return _merge_routing(
            self._globals.routing,
            domain.default_routing,
            category.routing if category is not None else None,
            getattr(url, "routing", None),
        )

    def resolve(
        self,
        url: _UrlLike | Url,
        category: Category | None,
        domain: Domain,
    ) -> tuple[CrawlConfig, DiffConfig, NotificationRouting]:
        """Return ``(crawl, diff, routing)`` in one call."""
        return (
            self.resolve_crawl(url, category, domain),
            self.resolve_diff(url, category, domain),
            self.resolve_routing(url, category, domain),
        )


class ChangeSignificanceEvaluator:
    """Apply L5 rules to decide whether a candidate change is significant.

    The evaluator is a pure function from ``(text, rules)`` to a boolean.
    It walks each rule in order, removing ignored text, and then enforces
    the trigger and exclusion constraints. Empty text after the rules run
    is treated as insignificant.
    """

    def evaluate(self, text: str, diff_config: DiffConfig) -> bool:
        """Return True when ``text`` survives all :class:`DiffConfig` rules.

        Rules are applied in this order:

        1. ``ignore_text`` / ``ignore_regex`` rules strip matching lines.
        2. ``trigger_text`` rules require at least one match in the result.
        3. ``text_must_not_be_present`` rules require zero matches.
        4. The final non-whitespace text must be at least ``min_text_length``.
        """
        cleaned = self._apply_ignore_rules(text, diff_config.significance_rules)
        if not self._triggers_match(cleaned, diff_config.significance_rules):
            return False
        return not (
            self._exclusion_present(cleaned, diff_config.significance_rules)
            or len(cleaned.strip()) < diff_config.min_text_length
        )

    @staticmethod
    def _apply_ignore_rules(text: str, rules: list[SignificanceRule]) -> str:
        kept_lines: list[str] = []
        for line in text.splitlines():
            if _should_ignore_line(line, rules):
                continue
            kept_lines.append(line)
        return "\n".join(kept_lines)

    @staticmethod
    def _triggers_match(text: str, rules: list[SignificanceRule]) -> bool:
        triggers = [r for r in rules if r.type.value == "trigger_text"]
        if not triggers:
            return True
        return any(_rule_matches(rule, text) for rule in triggers)

    @staticmethod
    def _exclusion_present(text: str, rules: list[SignificanceRule]) -> bool:
        exclusions = [r for r in rules if r.type.value == "text_must_not_be_present"]
        return any(_rule_matches(rule, text) for rule in exclusions)


def _rule_matches(rule: SignificanceRule, text: str) -> bool:
    """Return True if ``rule`` matches anywhere in ``text``."""
    if rule.is_regex:
        return re.search(rule.pattern, text) is not None
    return rule.pattern in text


def _should_ignore_line(line: str, rules: list[SignificanceRule]) -> bool:
    """Return True if any ``ignore_text`` rule matches ``line``."""
    for rule in rules:
        if rule.type.value != "ignore_text":
            continue
        if rule.is_regex:
            if re.search(rule.pattern, line):
                return True
        elif rule.pattern in line:
            return True
    return False


# ---------------------------------------------------------------------------
# NotificationRouter
# ---------------------------------------------------------------------------


_SCOPE_PRECEDENCE: dict[BindingScope, int] = {
    BindingScope.URL: 0,
    BindingScope.CATEGORY: 1,
    BindingScope.DOMAIN: 2,
    BindingScope.GLOBAL: 3,
}


@dataclass(frozen=True, slots=True)
class RouterRequest:
    """Inputs to :meth:`NotificationRouter.route`.

    Attributes:
        url_id: Id of the URL the event refers to.
        domain_id: Id of the URL's enclosing domain.
        category_id: Id of the URL's category, or ``None`` for an uncategorised URL.
        trigger: Trigger type of the event (``on_change`` / ``on_error`` / ``on_no_change``).
        bindings: All bindings potentially in scope (the router filters by scope ids and trigger).
        channels: Lookup of channel id to the loaded :class:`Channel` entity.
    """

    url_id: UUID
    domain_id: UUID
    category_id: UUID | None
    trigger: TriggerType
    bindings: tuple[ChannelBinding, ...]
    channels: dict[UUID, Channel]


def _binding_triggers_event(binding: ChannelBinding, trigger: TriggerType) -> bool:
    """Return True if the binding is set to fire for ``trigger``."""
    if trigger == TriggerType.ON_CHANGE:
        return binding.on_change
    if trigger == TriggerType.ON_ERROR:
        return binding.on_error
    return binding.on_no_change


def _binding_is_relevant(binding: ChannelBinding, request: RouterRequest) -> bool:
    """Return True if the binding's scope matches the event's url/domain/category."""
    if binding.scope == BindingScope.GLOBAL:
        return True
    if binding.scope == BindingScope.URL:
        return binding.scope_id == request.url_id
    if binding.scope == BindingScope.CATEGORY:
        return binding.scope_id is not None and binding.scope_id == request.category_id
    if binding.scope == BindingScope.DOMAIN:
        return binding.scope_id == request.domain_id
    return False


def _channel_id_override(
    request: RouterRequest,
    bindings: list[ChannelBinding],
) -> dict[UUID, BindingScope]:
    """Return the most specific scope per channel id (URL > Category > Domain > Global)."""
    overrides: dict[UUID, BindingScope] = {}
    for binding in bindings:
        scope = BindingScope(binding.scope)
        if scope not in _SCOPE_PRECEDENCE:
            continue
        if binding.channel_id not in overrides:
            overrides[binding.channel_id] = scope
            continue
        if _SCOPE_PRECEDENCE[scope] < _SCOPE_PRECEDENCE[overrides[binding.channel_id]]:
            overrides[binding.channel_id] = scope
    _ = request
    return overrides


class NotificationRouter:
    """Resolve the ordered, de-duplicated set of :class:`Channel` targets.

    Rules (in order):

    1. Filter bindings to those whose scope matches the event's scope ids
       (``url_id`` / ``category_id`` / ``domain_id`` / ``global``).
    2. Drop bindings whose trigger flag does not match the event's trigger.
    3. Sort the remaining bindings by scope precedence
       ``URL > Category > Domain > Global``.
    4. For each binding, include the channel if (a) it is loaded in the
       request, (b) the channel is enabled, and (c) no more specific binding
       for the same channel id has already been applied. The most specific
       scope that successfully fires wins.
    5. The output preserves the iteration order (most specific first).
    """

    def route(self, request: RouterRequest) -> list[Channel]:
        """Return the ordered, de-duplicated list of channels to notify."""
        eligible_bindings: list[ChannelBinding] = [
            binding
            for binding in request.bindings
            if _binding_is_relevant(binding, request) and _binding_triggers_event(binding, request.trigger)
        ]
        eligible_bindings.sort(
            key=lambda binding: _SCOPE_PRECEDENCE[BindingScope(binding.scope)],
        )
        overrides = _channel_id_override(request, eligible_bindings)

        delivered: dict[UUID, Channel] = {}
        for binding in eligible_bindings:
            channel = request.channels.get(binding.channel_id)
            if channel is None:
                continue
            if not channel.enabled:
                continue
            scope = BindingScope(binding.scope)
            if overrides.get(binding.channel_id) != scope:
                continue
            if binding.channel_id in delivered:
                continue
            delivered[binding.channel_id] = channel
        return list(delivered.values())
