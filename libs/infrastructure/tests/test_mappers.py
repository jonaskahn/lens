"""Mappers: ORM rows <-> domain entities round-trip."""

from __future__ import annotations

from datetime import UTC, datetime

from cryptography.fernet import Fernet
from uuid_extensions import uuid7

from lens_domain.entities import Category, Channel, ChannelBinding, Domain, Url
from lens_domain.enums import BindingScope, ChannelKind, UrlStatus
from lens_domain.ids import CategoryId, DomainId, UrlId
from lens_domain.value_objects import Hostname
from lens_infrastructure.db.mapping import (
    category_from_model,
    category_to_model,
    channel_binding_from_model,
    channel_binding_to_model,
    channel_from_model,
    channel_to_model,
    domain_from_model,
    domain_to_model,
    set_secret_cipher,
    url_from_model,
    url_to_model,
)
from lens_infrastructure.db.models import (
    DomainModel,
    UrlModel,
)
from lens_infrastructure.secrets import FernetSecretCipher

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_given_domain_when_to_model_then_round_trip() -> None:
    entity = Domain.create(
        id=DomainId(uuid7()),
        host="example.com",
        display_name="Example",
        now=NOW,
    )
    model = domain_to_model(entity)
    rebuilt = domain_from_model(model)
    assert rebuilt.host.value == entity.host.value
    assert rebuilt.display_name == entity.display_name
    assert rebuilt.enabled == entity.enabled
    assert rebuilt.id == entity.id


def test_given_category_when_to_model_then_round_trip() -> None:
    domain_id = DomainId(uuid7())
    entity = Category.create(
        id=CategoryId(uuid7()),
        domain_id=domain_id,
        name="products",
        description="Product pages",
        now=NOW,
    )
    model = category_to_model(entity)
    rebuilt = category_from_model(model)
    assert rebuilt.name == "products"
    assert rebuilt.description == "Product pages"
    assert rebuilt.domain_id == domain_id


def test_given_url_when_to_model_then_round_trip() -> None:
    domain_id = DomainId(uuid7())
    category_id = CategoryId(uuid7())
    entity = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain_id,
        address="https://example.com/p/1",
        interval_seconds=600,
        domain_host=Hostname(value="example.com"),
        category_id=category_id,
        now=NOW,
    )
    entity.status = UrlStatus.IDLE
    model = url_to_model(entity)
    rebuilt = url_from_model(model)
    assert rebuilt.address.value == "https://example.com/p/1"
    assert rebuilt.interval.seconds == 600
    assert rebuilt.category_id == category_id
    assert rebuilt.status == UrlStatus.IDLE


def test_given_channel_when_to_model_then_round_trip() -> None:
    entity = Channel.create(
        id=uuid7(),
        name="ops",
        kind=ChannelKind.SLACK,
        apprise_url="slack://token",
        enabled=True,
        now=NOW,
    )
    model = channel_to_model(entity)
    rebuilt = channel_from_model(model)
    assert rebuilt.name == "ops"
    assert rebuilt.kind == ChannelKind.SLACK
    assert rebuilt.apprise_url == "slack://token"
    assert rebuilt.enabled is True


def test_given_binding_when_to_model_then_round_trip() -> None:
    entity = ChannelBinding.create(
        id=uuid7(),
        channel_id=uuid7(),
        scope=BindingScope.DOMAIN,
        scope_id=uuid7(),
        on_change=True,
        on_error=True,
        on_no_change=False,
        now=NOW,
    )
    model = channel_binding_to_model(entity)
    rebuilt = channel_binding_from_model(model)
    assert rebuilt.scope == BindingScope.DOMAIN
    assert rebuilt.on_change is True
    assert rebuilt.on_error is True


def test_given_domain_model_with_defaults_when_from_model_then_defaults_apply() -> None:
    model = DomainModel(
        id=uuid7(),
        host="example.com",
        default_crawl_config={},
        default_diff_config={},
        politeness={},
        default_routing={},
        enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )
    entity = domain_from_model(model)
    assert entity.host.value == "example.com"
    assert entity.politeness.max_concurrency >= 1


def test_given_url_model_with_null_category_when_from_model_then_none() -> None:
    model = UrlModel(
        id=uuid7(),
        domain_id=uuid7(),
        address="https://example.com/p",
        interval_seconds=300,
        status="idle",
        enabled=True,
        consecutive_errors=0,
        next_due_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    entity = url_from_model(model)
    assert entity.category_id is None


def test_given_channel_when_fernet_cipher_active_then_round_trip() -> None:
    set_secret_cipher(FernetSecretCipher(Fernet.generate_key()))
    try:
        entity = Channel.create(
            id=uuid7(),
            name="ops",
            kind=ChannelKind.SLACK,
            apprise_url="slack://token",
            enabled=True,
            now=NOW,
        )
        model = channel_to_model(entity)
        assert model.apprise_url_encrypted != b"slack://token"
        rebuilt = channel_from_model(model)
        assert rebuilt.apprise_url == "slack://token"
    finally:
        set_secret_cipher(None)


def test_given_cipher_wrong_key_when_decrypt_then_raises() -> None:
    encrypt_cipher = FernetSecretCipher(Fernet.generate_key())
    decrypt_cipher = FernetSecretCipher(Fernet.generate_key())
    set_secret_cipher(encrypt_cipher)
    try:
        entity = Channel.create(
            id=uuid7(),
            name="ops",
            kind=ChannelKind.SLACK,
            apprise_url="slack://token",
            enabled=True,
            now=NOW,
        )
        model = channel_to_model(entity)
    finally:
        set_secret_cipher(None)
    set_secret_cipher(decrypt_cipher)
    try:
        import pytest

        from lens_infrastructure.secrets import SecretCipherError

        with pytest.raises(SecretCipherError):
            channel_from_model(model)
    finally:
        set_secret_cipher(None)
