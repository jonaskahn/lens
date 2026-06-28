"""Crawler worker package."""

from __future__ import annotations

from lens_crawler.main import (
    CrawlerWorkerComposition,
    build_crawler_worker,
)
from lens_crawler.settings import CrawlerWorkerSettings

__version__ = "0.1.0"

__all__ = [
    "CrawlerWorkerComposition",
    "CrawlerWorkerSettings",
    "build_crawler_worker",
]
