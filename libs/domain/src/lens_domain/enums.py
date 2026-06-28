"""Enumerations used across the domain layer.

All enums are :class:`enum.StrEnum` so they persist as plain text in the
database and serialize as their string value in JSON.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "BindingScope",
    "ChangeType",
    "ChannelKind",
    "EscalationReason",
    "FetchMethod",
    "LabelSource",
    "SignificanceRuleType",
    "TriggerType",
    "UrlStatus",
]


class UrlStatus(StrEnum):
    """Persisted status of a tracked :class:`Url`."""

    IDLE = "idle"
    ENQUEUED = "enqueued"
    CRAWLING = "crawling"
    ERROR = "error"
    DISABLED = "disabled"


class BindingScope(StrEnum):
    """Scope at which a :class:`ChannelBinding` applies."""

    GLOBAL = "global"
    DOMAIN = "domain"
    CATEGORY = "category"
    URL = "url"


class ChannelKind(StrEnum):
    """The kind of a notification :class:`Channel`."""

    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"


class TriggerType(StrEnum):
    """Notification trigger type."""

    ON_CHANGE = "on_change"
    ON_ERROR = "on_error"
    ON_NO_CHANGE = "on_no_change"


class SignificanceRuleType(StrEnum):
    """L5 significance-rule categories."""

    IGNORE_TEXT = "ignore_text"
    TRIGGER_TEXT = "trigger_text"
    TEXT_MUST_NOT_BE_PRESENT = "text_must_not_be_present"


class FetchMethod(StrEnum):
    """The method used to fetch a URL."""

    CRAWL4AI = "crawl4ai"


class ChangeType(StrEnum):
    """AI-enrichment change classification (only used when AI_ENABLED)."""

    CONTENT = "content"
    PRICE = "price"
    STOCK = "stock"
    LEGAL = "legal"
    LAYOUT = "layout"
    COSMETIC = "cosmetic"
    OTHER = "other"


class EscalationReason(StrEnum):
    """Reasons a change may be escalated to the AI tier."""

    SIGNAL_DISAGREEMENT = "signal_disagreement"
    HIGH_VALUE_ZONE = "high_value_zone"
    GRAY_BAND = "gray_band"
    TEMPLATE_DRIFT = "template_drift"
    FORCED = "forced"


class LabelSource(StrEnum):
    """Who produced a :class:`ChangeLabel`."""

    HUMAN = "human"
    LLM = "llm"
    RULE = "rule"
