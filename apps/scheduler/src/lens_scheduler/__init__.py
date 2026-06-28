"""Scheduler package."""

from __future__ import annotations

from lens_scheduler.main import SchedulerComposition, build_scheduler
from lens_scheduler.settings import SchedulerSettings

__version__ = "0.1.0"

__all__ = [
    "SchedulerComposition",
    "SchedulerSettings",
    "build_scheduler",
]
