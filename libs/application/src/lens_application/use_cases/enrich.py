"""AI enrichment use case: L6 LLM classification tier (behind escalation gate).

The :class:`EnrichChangeUseCase` runs in the ``ai_worker`` role, consuming
``ChangeNeedsEnrichment`` tasks from the broker. It loads the changed-zone
diffs, calls the LLM via :class:`ChangeClassifierPort`, persists the
classification, and emits a ``ChangeEnriched`` outbox event.

All AI use cases are pure application logic: they orchestrate the classifier
port, persistence ports, and the outbox. No LLM/embedding code is imported here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from lens_application.dto import EnrichResult
from lens_application.pipeline import ChangeClassifierPort, ClassifyRequest
from lens_application.ports import UnitOfWork
from lens_application.use_cases._base import UseCase
from lens_domain.events import ChangeEnriched
from lens_domain.value_objects import ChangeClassification, ChangeLabel

__all__ = ["EnrichChangeUseCase"]


def _build_classification_payload(classification: ChangeClassification) -> dict[str, Any]:
    return {
        "change_type": classification.change_type.value,
        "is_meaningful": classification.is_meaningful,
        "severity": classification.severity,
        "summary": classification.summary,
        "extracted_fields": classification.extracted_fields,
        "confidence": classification.confidence,
        "model_id": classification.model_id,
        "tokens_used": classification.tokens_used,
    }


class EnrichChangeUseCase(UseCase[dict[str, Any], EnrichResult]):
    """Classify a single escalated change via the LLM and persist the result.

    The use case is idempotent on ``change_id``: if a classification
    already exists for the given change, it is returned immediately
    without calling the LLM.

    A weak label (``labeled_by='llm'``) is written on each successful
    enrichment, feeding the auto-learning loop (P6, ``12`` §6).
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        classifier: ChangeClassifierPort,
    ) -> None:
        super().__init__(uow_factory)
        self._classifier = classifier

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> EnrichResult:
        change_id: UUID = params["change_id"]
        url_id: UUID = params["url_id"]
        domain_id: UUID = params["domain_id"]
        category_id: UUID | None = params.get("category_id")
        prev_text: str = params.get("prev_text", "")
        curr_text: str = params.get("curr_text", "")
        zone_name: str = params.get("zone_name", "")
        template_class: str | None = params.get("template_class")

        existing = await uow.change_classifications.get(change_id)
        if existing is not None:
            return EnrichResult(
                change_id=change_id,
                enrichment_status="enriched",
                classification=existing,
                enriched_event_emitted=False,
            )

        request = ClassifyRequest(
            change_id=change_id,
            prev_text=prev_text,
            curr_text=curr_text,
            zone_name=zone_name,
            template_class=template_class,
        )

        classification = await self._classifier.classify(request)
        tokens_used = classification.tokens_used
        llm_latency_ms = classification.latency_ms

        await uow.change_classifications.add(
            change_id=change_id,
            classification=_build_classification_payload(classification),
            model_id=classification.model_id or "unknown",
            tokens_used=tokens_used,
            llm_latency_ms=llm_latency_ms,
        )

        await uow.change_labels.add(
            ChangeLabel(
                change_id=change_id,
                is_change=True,
                is_meaningful=classification.is_meaningful,
                change_type=classification.change_type.value,
                labeled_by="llm",
            )
        )

        await uow.changes.update_enrichment_status(change_id, "enriched")

        now = uow.now()
        enriched_event_id = uow.new_id()
        event = ChangeEnriched(
            event_id=enriched_event_id,
            occurred_at=now,
            url_id=url_id,
            change_id=change_id,
            domain_id=domain_id,
            category_id=category_id,
            classification=_build_classification_payload(classification),
        )

        outbox_id = uow.new_id()
        await uow.outbox.add(
            id=outbox_id,
            aggregate_type="change",
            aggregate_id=change_id,
            event_type=event.__class__.__name__,
            event_id=event.event_id,
            payload={
                "url_id": str(event.url_id),
                "change_id": str(event.change_id),
                "domain_id": str(event.domain_id),
                "category_id": str(event.category_id) if event.category_id is not None else None,
                "classification": event.classification,
            },
            created_at=now,
        )
        await uow.flush()

        return EnrichResult(
            change_id=change_id,
            enrichment_status="enriched",
            classification=_build_classification_payload(classification),
            enriched_event_emitted=True,
            escalation_reasons=list(
                params.get("escalation_reasons", []),
            ),
        )
