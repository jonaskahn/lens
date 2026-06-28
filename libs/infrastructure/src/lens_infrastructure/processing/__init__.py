"""L2-L4 pipeline adapters: fingerprint, zone extractor, scorer, classifier."""

from lens_infrastructure.processing.classifier import TemplateClassifier
from lens_infrastructure.processing.fingerprint import TemplateFingerprint
from lens_infrastructure.processing.scorer import SemanticScorer
from lens_infrastructure.processing.zones import ZoneExtractor

__all__ = [
    "SemanticScorer",
    "TemplateClassifier",
    "TemplateFingerprint",
    "ZoneExtractor",
]
