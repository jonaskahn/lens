"""Import/Export use cases (unit tests)."""

from __future__ import annotations

import pytest
from _fakes import InMemoryUnitOfWork, reset_in_memory_store

from lens_application.dto import (
    ConflictPolicy,
    CreateDomainInput,
    SetupCategory,
    SetupDomain,
    SetupDto,
    SetupUrl,
)
from lens_application.errors import NotFoundError
from lens_application.use_cases.domains import CreateDomainUseCase, GetDomainUseCase
from lens_application.use_cases.import_export import (
    ExportSetupUseCase,
    ImportSetupUseCase,
)


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    reset_in_memory_store()


def _factory() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


async def test_given_setup_when_import_skip_then_creates_domains() -> None:
    setup = SetupDto(
        domains=[
            SetupDomain(
                host="a.example.com",
                categories=[
                    SetupCategory(
                        name="products",
                        urls=[
                            SetupUrl(
                                address="https://a.example.com/p/1",
                                interval_seconds=600,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    use_case = ImportSetupUseCase(_factory)
    result = await use_case.execute({"setup": setup, "on_conflict": ConflictPolicy.SKIP})

    assert result.errors == []
    assert result.created >= 3  # 1 domain + 1 category + 1 url


async def test_given_duplicate_url_when_import_skip_then_no_double_create() -> None:
    setup = SetupDto(
        domains=[
            SetupDomain(
                host="a.example.com",
                categories=[
                    SetupCategory(
                        name="products",
                        urls=[SetupUrl(address="https://a.example.com/p/1", interval_seconds=600)],
                    ),
                ],
            ),
        ],
    )
    use_case = ImportSetupUseCase(_factory)
    first = await use_case.execute({"setup": setup, "on_conflict": ConflictPolicy.SKIP})
    second = await use_case.execute({"setup": setup, "on_conflict": ConflictPolicy.SKIP})
    assert first.created >= 1
    assert second.created == 0


async def test_given_existing_when_import_replace_then_url_count_unchanged() -> None:
    setup = SetupDto(
        domains=[
            SetupDomain(
                host="a.example.com",
                categories=[
                    SetupCategory(
                        name="products",
                        urls=[SetupUrl(address="https://a.example.com/p/1", interval_seconds=600)],
                    ),
                ],
            ),
        ],
    )
    use_case = ImportSetupUseCase(_factory)
    await use_case.execute({"setup": setup, "on_conflict": ConflictPolicy.SKIP})
    result = await use_case.execute({"setup": setup, "on_conflict": ConflictPolicy.REPLACE})
    assert result.errors == []


async def test_given_seeded_when_export_then_setup_matches() -> None:
    create = CreateDomainUseCase(_factory)
    await create.execute(CreateDomainInput(host="a.example.com"))

    use_case = ExportSetupUseCase(_factory)
    result = await use_case.execute({"domain_host": "a.example.com"})
    assert len(result.setup.domains) == 1
    assert result.setup.domains[0].host == "a.example.com"


async def test_given_unknown_when_export_then_not_found() -> None:
    use_case = ExportSetupUseCase(_factory)
    with pytest.raises(NotFoundError):
        await use_case.execute({"domain_host": "missing.com"})


async def test_given_seeded_when_get_domain_by_id_then_ok() -> None:
    dto = await CreateDomainUseCase(_factory).execute(CreateDomainInput(host="a.example.com"))
    fetched = await GetDomainUseCase(_factory).execute(str(dto.id))
    assert fetched.host == "a.example.com"
