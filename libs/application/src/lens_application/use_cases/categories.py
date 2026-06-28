"""Category CRUD use cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lens_application.dto import (
    CategoryDto,
    CreateCategoryInput,
    ListResult,
    UpdateCategoryInput,
)
from lens_application.errors import ConflictError, NotFoundError
from lens_application.ports import UnitOfWork
from lens_application.use_cases._base import UseCase
from lens_application.use_cases._mapping import category_to_dto
from lens_domain.entities import Category
from lens_domain.ids import CategoryId, DomainId

__all__ = [
    "CreateCategoryUseCase",
    "DeleteCategoryUseCase",
    "GetCategoryUseCase",
    "ListCategoriesUseCase",
    "UpdateCategoryUseCase",
]


class CreateCategoryUseCase(UseCase[CreateCategoryInput, CategoryDto]):
    """Create a new :class:`Category` under a :class:`Domain`."""

    async def run(self, input_dto: CreateCategoryInput, uow: UnitOfWork) -> CategoryDto:
        domain = await uow.domains.get(input_dto.domain_id)
        if domain is None:
            raise NotFoundError(f"domain not found: {input_dto.domain_id!s}")
        existing = await uow.categories.get_by_name(input_dto.domain_id, input_dto.name)
        if existing is not None:
            raise ConflictError(
                f"category {input_dto.name!r} already exists in domain",
                details={"name": input_dto.name},
            )
        entity = Category.create(
            id=CategoryId(uow.new_id()),
            domain_id=DomainId(input_dto.domain_id),
            name=input_dto.name,
            description=input_dto.description,
            now=uow.now(),
        )
        await uow.categories.add(entity)
        await uow.flush()
        return category_to_dto(entity)


class GetCategoryUseCase(UseCase[UUID, CategoryDto]):
    """Fetch a single :class:`Category` by id."""

    async def run(self, category_id: UUID, uow: UnitOfWork) -> CategoryDto:
        entity = await uow.categories.get(category_id)
        if entity is None:
            raise NotFoundError(f"category not found: {category_id!s}")
        return category_to_dto(entity)


class ListCategoriesUseCase(UseCase[dict[str, Any], ListResult[CategoryDto]]):
    """List categories of a :class:`Domain`."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ListResult[CategoryDto]:
        domain_id: UUID | None = params.get("domain_id")
        cursor = params.get("cursor")
        limit = params.get("limit", 50)
        if domain_id is not None:
            entities, next_cursor = await uow.categories.list_by_domain(
                domain_id=domain_id,
                cursor=cursor,
                limit=limit,
            )
        else:
            entities, next_cursor = await uow.categories.list(cursor=cursor, limit=limit)
        return ListResult[CategoryDto](
            items=[category_to_dto(c) for c in entities],
            next_cursor=next_cursor,
        )


class UpdateCategoryUseCase(UseCase[dict[str, Any], CategoryDto]):
    """Replace mutable fields on a :class:`Category`."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> CategoryDto:
        category_id: UUID = params["id"]
        input_dto: UpdateCategoryInput = params["input"]
        entity = await uow.categories.get(category_id)
        if entity is None:
            raise NotFoundError(f"category not found: {category_id!s}")
        entity.update(
            name=input_dto.name,
            description=input_dto.description,
            now=uow.now(),
        )
        await uow.categories.update(entity)
        await uow.flush()
        return category_to_dto(entity)


class DeleteCategoryUseCase(UseCase[UUID, None]):
    """Delete a :class:`Category`."""

    async def run(self, category_id: UUID, uow: UnitOfWork) -> None:
        existing = await uow.categories.get(category_id)
        if existing is None:
            raise NotFoundError(f"category not found: {category_id!s}")
        await uow.categories.delete(category_id)
