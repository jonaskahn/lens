"""Domain CRUD use cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lens_application.dto import (
    CreateDomainInput,
    DomainDto,
    ListResult,
    UpdateDomainInput,
)
from lens_application.errors import ConflictError, NotFoundError
from lens_application.ports import UnitOfWork
from lens_application.use_cases._base import UseCase
from lens_application.use_cases._mapping import domain_to_dto
from lens_domain.entities import Domain
from lens_domain.ids import DomainId

__all__ = [
    "CreateDomainUseCase",
    "DeleteDomainUseCase",
    "GetDomainUseCase",
    "ListDomainsUseCase",
    "UpdateDomainUseCase",
]


class CreateDomainUseCase(UseCase[CreateDomainInput, DomainDto]):
    """Create a new :class:`Domain`."""

    async def run(self, input_dto: CreateDomainInput, uow: UnitOfWork) -> DomainDto:
        existing = await uow.domains.get_by_host(input_dto.host)
        if existing is not None:
            raise ConflictError(
                f"domain with host {input_dto.host!r} already exists",
                details={"host": input_dto.host},
            )
        entity = Domain.create(
            id=DomainId(uow.new_id()),
            host=input_dto.host,
            display_name=input_dto.display_name,
            enabled=input_dto.enabled,
            now=uow.now(),
        )
        await uow.domains.add(entity)
        await uow.flush()
        return domain_to_dto(entity)


class GetDomainUseCase(UseCase[str, DomainDto]):
    """Fetch a single :class:`Domain` by id or host."""

    async def run(self, identifier: str, uow: UnitOfWork) -> DomainDto:
        parsed: UUID | None = None
        try:
            parsed = UUID(identifier)
        except ValueError:
            parsed = None
        entity = await uow.domains.get(parsed) if parsed is not None else None
        if entity is None:
            entity = await uow.domains.get_by_host(identifier)
        if entity is None:
            raise NotFoundError(f"domain not found: {identifier!r}")
        return domain_to_dto(entity)


class ListDomainsUseCase(UseCase[dict[str, Any], ListResult[DomainDto]]):
    """List domains with optional ``enabled``/search filters and pagination."""

    async def run(
        self,
        params: dict[str, Any],
        uow: UnitOfWork,
    ) -> ListResult[DomainDto]:
        entities, next_cursor = await uow.domains.list(
            enabled=params.get("enabled"),
            search=params.get("search"),
            cursor=params.get("cursor"),
            limit=params.get("limit", 50),
        )
        return ListResult[DomainDto](
            items=[domain_to_dto(d) for d in entities],
            next_cursor=next_cursor,
        )


class UpdateDomainUseCase(UseCase[dict[str, Any], DomainDto]):
    """Replace mutable fields on a :class:`Domain`."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> DomainDto:
        domain_id: UUID = params["id"]
        input_dto: UpdateDomainInput = params["input"]
        entity = await uow.domains.get(domain_id)
        if entity is None:
            raise NotFoundError(f"domain not found: {domain_id!s}")
        entity.update(
            display_name=input_dto.display_name,
            enabled=input_dto.enabled,
            now=uow.now(),
        )
        await uow.domains.update(entity)
        await uow.flush()
        return domain_to_dto(entity)


class DeleteDomainUseCase(UseCase[UUID, None]):
    """Delete a :class:`Domain` (cascades to categories/urls)."""

    async def run(self, domain_id: UUID, uow: UnitOfWork) -> None:
        existing = await uow.domains.get(domain_id)
        if existing is None:
            raise NotFoundError(f"domain not found: {domain_id!s}")
        await uow.domains.delete(domain_id)
