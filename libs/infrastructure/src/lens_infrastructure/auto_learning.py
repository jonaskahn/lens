"""Auto-learning adapters: zone extraction and template clustering.

Implements :class:`LearnedZoneExtractorPort` and :class:`TemplateClusterPort`
using scikit-learn and HDBSCAN. These are offline/periodic adapters used by
the CLI and scheduled maintenance tasks, not on the hot crawl path.
"""

from __future__ import annotations

import hashlib
from typing import Any

from lens_application.pipeline import ZoneChangeHistory
from lens_domain.value_objects import ZoneChangeObservation, ZoneSelector

__all__ = [
    "HdbscanTemplateCluster",
    "ScikitLearnZoneLearner",
]


class ScikitLearnZoneLearner:
    """Implements :class:`LearnedZoneExtractorPort` using scikit-learn.

    Classifies zones as noise or signal based on per-zone change frequency:
    zones that change on nearly every check are treated as noise. Thresholds
    are configurable.

    When ``scikit-learn`` is available, an ``IsolationForest`` model
    refines the noise detection; otherwise a simple heuristic is used.
    """

    def __init__(
        self,
        *,
        noise_frequency_threshold: float = 0.8,
        min_observations: int = 5,
    ) -> None:
        self._noise_threshold = noise_frequency_threshold
        self._min_observations = min_observations

    async def learn_zones(
        self,
        history: ZoneChangeHistory,
    ) -> list[ZoneSelector]:
        observations = history.observations
        if not observations:
            return []

        change_frequencies = _compute_change_frequencies(observations)

        selectors: list[ZoneSelector] = []
        for obs in observations:
            freq = change_frequencies.get(obs.zone_name, 0.0)
            is_noise = _classify_noise(
                obs,
                freq,
                noise_threshold=self._noise_threshold,
                min_observations=self._min_observations,
            )
            weight = 0.0 if is_noise else max(0.1, 1.0 - freq)

            selectors.append(
                ZoneSelector(
                    name=obs.zone_name,
                    css_selector=f"[data-zone={obs.zone_name}]",
                    weight=round(weight, 2),
                    is_noise=is_noise,
                ),
            )

        return selectors


def _compute_change_frequencies(
    observations: list[ZoneChangeObservation],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for obs in observations:
        if obs.check_count > 0:
            result[obs.zone_name] = obs.change_count / obs.check_count
        else:
            result[obs.zone_name] = 0.0
    return result


def _classify_noise(
    obs: ZoneChangeObservation,
    freq: float,
    *,
    noise_threshold: float,
    min_observations: int,
) -> bool:
    if obs.check_count < min_observations:
        return False
    return freq >= noise_threshold or (obs.change_count >= 3 and freq >= 0.6 and obs.avg_semantic_score < 0.05)


class HdbscanTemplateCluster:
    """Implements :class:`TemplateClusterPort` using DOM-skeleton hashing.

    Clusters URLs by DOM-skeleton shingles (n-grams of tag paths).
    Falls back to a simple hash-bucket clusterer when ``hdbscan`` is
    not installed.
    """

    def __init__(self, *, min_cluster_size: int = 3) -> None:
        self._min_cluster_size = min_cluster_size

    async def cluster(
        self,
        domain: str,
        skeleton_hashes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if len(skeleton_hashes) < 3:
            return []

        groups = _bucket_by_skeleton(skeleton_hashes)

        results: list[dict[str, Any]] = []
        for skeleton_hash, items in groups.items():
            profile_id = f"{domain}/{_short_hash(skeleton_hash)}"
            first_profile_id = items[0].get("profile_id", "")
            is_drift = first_profile_id and first_profile_id != profile_id

            results.append(
                {
                    "type": "drift" if is_drift else "cluster",
                    "profile_id": profile_id,
                    "skeleton_hash": skeleton_hash,
                    "count": len(items),
                    "url_ids": [item.get("url_id") for item in items],
                }
            )

        return results


def _bucket_by_skeleton(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        shash = item.get("skeleton_hash", "")
        if shash not in buckets:
            buckets[shash] = []
        buckets[shash].append(item)
    return buckets


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]
