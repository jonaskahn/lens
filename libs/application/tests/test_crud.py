"""Domain CRUD use cases (unit tests with in-memory fakes)."""

from __future__ import annotations

import pytest
from _fakes import InMemoryUnitOfWork, reset_in_memory_store

from lens_application.dto import (
    CreateDomainInput,
    CreateUrlInput,
    UpdateDomainInput,
)
from lens_application.errors import ConflictError, NotFoundError
from lens_application.use_cases.domains import (
    CreateDomainUseCase,
    DeleteDomainUseCase,
    GetDomainUseCase,
    ListDomainsUseCase,
    UpdateDomainUseCase,
)
from lens_application.use_cases.urls import CreateUrlUseCase


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    """Ensure each test starts with an empty in-memory store."""
    reset_in_memory_store()


def _factory() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


async def test_given_valid_input_when_create_domain_then_persisted() -> None:
    use_case = CreateDomainUseCase(_factory)
    dto = await use_case.execute(
        CreateDomainInput(
            host="shop.example.com",
            display_name="Shop",
            enabled=True,
        ),
    )
    assert dto.host == "shop.example.com"
    assert dto.display_name == "Shop"
    fetched = await GetDomainUseCase(_factory).execute("shop.example.com")
    assert fetched.id == dto.id


async def test_given_duplicate_host_when_create_domain_then_conflict() -> None:
    use_case = CreateDomainUseCase(_factory)
    await use_case.execute(CreateDomainInput(host="shop.example.com"))

    with pytest.raises(ConflictError):
        await use_case.execute(CreateDomainInput(host="SHOP.example.com"))


async def test_given_unknown_id_when_get_domain_then_not_found() -> None:
    use_case = GetDomainUseCase(_factory)
    with pytest.raises(NotFoundError):
        await use_case.execute("missing")


async def test_given_existing_when_get_domain_by_host_then_ok() -> None:
    create = CreateDomainUseCase(_factory)
    await create.execute(CreateDomainInput(host="news.example.com"))

    get = GetDomainUseCase(_factory)
    dto = await get.execute("news.example.com")
    assert dto.host == "news.example.com"


async def test_given_seeded_when_list_domains_then_returns_all() -> None:
    create = CreateDomainUseCase(_factory)
    await create.execute(CreateDomainInput(host="a.example.com"))
    await create.execute(CreateDomainInput(host="b.example.com"))

    lst = ListDomainsUseCase(_factory)
    result = await lst.execute({})
    assert len(result.items) == 2


async def test_given_seeded_when_update_domain_then_field_changes() -> None:
    create = CreateDomainUseCase(_factory)
    dto = await create.execute(CreateDomainInput(host="a.example.com", display_name="Old"))

    update = UpdateDomainUseCase(_factory)
    updated = await update.execute({"id": dto.id, "input": UpdateDomainInput(display_name="New")})
    assert updated.display_name == "New"


async def test_given_seeded_when_delete_domain_then_gone() -> None:
    create = CreateDomainUseCase(_factory)
    dto = await create.execute(CreateDomainInput(host="a.example.com"))

    delete = DeleteDomainUseCase(_factory)
    await delete.execute(dto.id)
    get = GetDomainUseCase(_factory)
    with pytest.raises(NotFoundError):
        await get.execute(str(dto.id))


async def test_given_url_with_matching_host_when_create_then_ok() -> None:
    domain_dto = await CreateDomainUseCase(_factory).execute(
        CreateDomainInput(host="shop.example.com"),
    )
    url_dto = await CreateUrlUseCase(_factory).execute(
        CreateUrlInput(
            domain_id=domain_dto.id,
            address="https://shop.example.com/p/1",
            interval_seconds=600,
        ),
    )
    assert url_dto.address == "https://shop.example.com/p/1"
    assert url_dto.interval_seconds == 600
    assert url_dto.status == "idle"


async def test_given_url_with_mismatched_host_when_create_then_conflict() -> None:
    domain_dto = await CreateDomainUseCase(_factory).execute(
        CreateDomainInput(host="shop.example.com"),
    )
    create = CreateUrlUseCase(_factory)
    with pytest.raises(ConflictError):
        await create.execute(
            CreateUrlInput(
                domain_id=domain_dto.id,
                address="https://other.com/p/1",
                interval_seconds=600,
            ),
        )
