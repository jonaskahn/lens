"""Auto-learning use cases: zone learning, template clustering, eval pipeline, labeling.

All use cases are pure application logic: they orchestrate existing ports
and persistence boundaries. No ML/embedding code is imported here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from lens_application.dto import (
    ClusterTemplatesResult,
    EvalPipelineResult,
    LabelResult,
    LearnZonesResult,
)
from lens_application.pipeline import (
    EmbeddingScorerPort,
    LearnedZoneExtractorPort,
    SemanticScorerPort,
    TemplateClusterPort,
    ZoneChangeHistory,
)
from lens_application.ports import (
    ChangeClassificationRepository,
    ChangeLabelRepository,
    UnitOfWork,
)
from lens_application.use_cases._base import UseCase
from lens_domain.value_objects import ChangeLabel, ZoneChangeObservation

__all__ = [
    "ClusterTemplatesUseCase",
    "EvalPipelineUseCase",
    "LabelChangesUseCase",
    "LearnZonesUseCase",
]


class LearnZonesUseCase(UseCase[dict[str, Any], LearnZonesResult]):
    """Mine zone change history to classify noise vs signal zones.

    Drives :class:`LearnedZoneExtractorPort` for a given domain/profile,
    consuming per-zone observations from the DB and optionally weak labels
    from :class:`ChangeLabelRepository`. Writes learned selectors back to
    the :class:`SiteProfile` in ``--dry-run`` mode, or persists when
    ``dry_run=False``.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        learner: LearnedZoneExtractorPort,
        label_repo: ChangeLabelRepository,
    ) -> None:
        super().__init__(uow_factory)
        self._learner = learner
        self._label_repo = label_repo

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> LearnZonesResult:
        domain: str = params.get("domain", "")
        profile_id: UUID | None = params.get("profile_id")
        dry_run: bool = params.get("dry_run", True)
        observations_data: list[dict[str, Any]] = params.get("observations", [])

        observations = [
            ZoneChangeObservation(
                zone_name=obs.get("zone_name", ""),
                check_count=obs.get("check_count", 0),
                change_count=obs.get("change_count", 0),
                avg_semantic_score=obs.get("avg_semantic_score", 0.0),
                labeled_changes=obs.get("labeled_changes", 0),
                labeled_meaningful=obs.get("labeled_meaningful", 0),
            )
            for obs in observations_data
        ]

        total_checks = params.get("total_checks", 0)
        total_changes = params.get("total_changes", 0)

        history = ZoneChangeHistory(
            profile_id=profile_id,
            domain=domain,
            observations=observations,
            total_checks=total_checks,
            total_changes=total_changes,
        )

        learned = await self._learner.learn_zones(history)

        noise_zones = [z.name for z in learned if z.is_noise]
        signal_zones = [z.name for z in learned if not z.is_noise]

        zone_dicts: list[dict[str, Any]] = [
            {
                "name": z.name,
                "css_selector": z.css_selector,
                "weight": z.weight,
                "is_noise": z.is_noise,
            }
            for z in learned
        ]

        if not dry_run and profile_id is not None:
            profile_repo = getattr(uow, "site_profiles", None)
            if profile_repo is not None and hasattr(profile_repo, "upsert_zones"):
                await profile_repo.upsert_zones(
                    profile_id=str(profile_id),
                    selectors=zone_dicts,
                )

        return LearnZonesResult(
            profile_id=profile_id,
            zone_selectors=zone_dicts,
            noise_zones=noise_zones,
            signal_zones=signal_zones,
            observations_used=len(observations),
        )


class ClusterTemplatesUseCase(UseCase[dict[str, Any], ClusterTemplatesResult]):
    """Cluster URLs into template profiles and detect structural drift.

    Drives :class:`TemplateClusterPort` on DOM-skeleton hashes for a
    domain; returns cluster assignments and profiles flagged for drift.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        clusterer: TemplateClusterPort,
    ) -> None:
        super().__init__(uow_factory)
        self._clusterer = clusterer

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ClusterTemplatesResult:
        domain: str = params.get("domain", "")
        skeleton_data: list[dict[str, Any]] = params.get("skeletons", [])

        results = await self._clusterer.cluster(domain, skeleton_data)

        clusters: list[dict[str, Any]] = []
        drift_profiles: list[str] = []
        for r in results:
            if r.get("type") == "drift":
                drift_profiles.append(r.get("profile_id", ""))
            else:
                clusters.append(r)

        return ClusterTemplatesResult(
            domain=domain,
            clusters=clusters,
            drift_profiles=drift_profiles,
            urls_clustered=len(skeleton_data),
        )


class EvalPipelineUseCase(UseCase[dict[str, Any], EvalPipelineResult]):
    """Replay stored changes through L4 + gate against labeled data.

    Reports precision/recall of "meaningful" detection, false-positive
    reduction vs lexical-only scoring, realized escalation rate, and
    per-template-class score distributions.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        lexical_scorer: SemanticScorerPort,
        embedding_scorer: EmbeddingScorerPort | None = None,
        label_repo: ChangeLabelRepository | None = None,
        classification_repo: ChangeClassificationRepository | None = None,
    ) -> None:
        super().__init__(uow_factory)
        self._lexical_scorer = lexical_scorer
        self._embedding_scorer = embedding_scorer
        self._label_repo = label_repo
        self._classification_repo = classification_repo

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> EvalPipelineResult:
        changes_data: list[dict[str, Any]] = params.get("changes", [])
        labels_data: list[dict[str, Any]] = params.get("labels", [])

        labels_by_change: dict[str, dict[str, Any]] = {}
        for label in labels_data:
            cid = str(label.get("change_id", ""))
            if cid:
                labels_by_change[cid] = label

        tp = 0
        fp = 0
        tn = 0
        fn = 0
        escalated = 0
        esc_reasons: dict[str, int] = {}
        per_class: dict[str, dict[str, int]] = {}
        lexical_only_fp = 0

        for change in changes_data:
            change_id = str(change.get("change_id", ""))
            prev_text = change.get("prev_text", "")
            curr_text = change.get("curr_text", "")
            label = labels_by_change.get(change_id, {})
            is_labeled_meaningful = label.get("is_meaningful", False)
            template_class = change.get("template_class", "unknown")

            lexical_score = self._lexical_scorer.score(prev_text, curr_text)
            semantic_score = 0.0
            if self._embedding_scorer is not None:
                semantic_score = await self._embedding_scorer.semantic_distance(
                    prev_text,
                    curr_text,
                )

            combined = max(lexical_score, semantic_score) if semantic_score else lexical_score
            predicted = combined >= 0.05

            if predicted and is_labeled_meaningful:
                tp += 1
            elif predicted and not is_labeled_meaningful:
                fp += 1
                if lexical_score >= 0.05:
                    lexical_only_fp += 1
            elif not predicted and not is_labeled_meaningful:
                tn += 1
            elif not predicted and is_labeled_meaningful:
                fn += 1

            escalated_bool = change.get("escalated", False)
            if escalated_bool:
                escalated += 1
                for reason in change.get("escalation_reasons", []):
                    esc_reasons[reason] = esc_reasons.get(reason, 0) + 1

            if template_class not in per_class:
                per_class[template_class] = {
                    "tp": 0,
                    "fp": 0,
                    "tn": 0,
                    "fn": 0,
                    "total": 0,
                }
            if predicted and is_labeled_meaningful:
                bucket = "tp"
            elif predicted and not is_labeled_meaningful:
                bucket = "fp"
            elif not predicted and not is_labeled_meaningful:
                bucket = "tn"
            else:
                bucket = "fn"
            per_class[template_class][bucket] += 1
            per_class[template_class]["total"] += 1

        total = tp + fp + tn + fn
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        esc_rate = escalated / total if total > 0 else 0.0
        fps_vs_lexical = (fp - lexical_only_fp) / fp if fp > 0 else 0.0

        return EvalPipelineResult(
            total_changes=total,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            escalation_rate=round(esc_rate, 4),
            fps_vs_lexical_only=round(fps_vs_lexical, 4),
            per_class_distributions=per_class,
        )


class LabelChangesUseCase(UseCase[dict[str, Any], LabelResult]):
    """Sample changes for hand-labeling or bulk-label via LLM.

    Writes :class:`ChangeLabel` rows to the DB, keyed by
    ``(change_id, labeled_by)``.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        label_repo: ChangeLabelRepository | None = None,
    ) -> None:
        super().__init__(uow_factory)
        self._label_repo = label_repo

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> LabelResult:
        labels_data: list[dict[str, Any]] = params.get("labels", [])
        labeled: int = 0
        errors: list[str] = []

        repo = self._label_repo if self._label_repo is not None else uow.change_labels

        for item in labels_data:
            try:
                change_id = UUID(str(item["change_id"]))
                label = ChangeLabel(
                    change_id=change_id,
                    is_change=bool(item.get("is_change", True)),
                    is_meaningful=item.get("is_meaningful"),
                    change_type=item.get("change_type"),
                    labeled_by=str(item.get("labeled_by", "human")),
                )
                await repo.add(label)
                labeled += 1
            except Exception as exc:
                errors.append(str(exc))

        return LabelResult(
            labeled=labeled,
            errors=errors,
        )
