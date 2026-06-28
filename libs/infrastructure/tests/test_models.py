"""SQLAlchemy ORM models: introspect the declared tables."""

from __future__ import annotations

from lens_infrastructure.db.base import Base
from lens_infrastructure.db.models import (
    ApiKeyModel,
    CategoryModel,
    ChannelBindingModel,
    ChannelModel,
    DomainModel,
    UrlModel,
)


def test_given_models_when_metadata_introspected_then_all_tables_present() -> None:
    tables = set(Base.metadata.tables)
    expected = {
        "domains",
        "categories",
        "urls",
        "channels",
        "channel_bindings",
        "api_keys",
    }
    assert expected.issubset(tables)
    assert DomainModel.__tablename__ == "domains"
    assert CategoryModel.__tablename__ == "categories"
    assert UrlModel.__tablename__ == "urls"
    assert ChannelModel.__tablename__ == "channels"
    assert ChannelBindingModel.__tablename__ == "channel_bindings"
    assert ApiKeyModel.__tablename__ == "api_keys"
