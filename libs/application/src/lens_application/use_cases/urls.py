"""Url CRUD use cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lens_application.dto import (
    CreateUrlInput,
    ListResult,
    UpdateUrlInput,
    UrlDto,
)
from lens_application.errors import ConflictError, NotFoundError, ValidationFailed
from lens_application.ports import UnitOfWork
from lens_application.use_cases._base import UseCase
from lens_application.use_cases._mapping import url_to_dto
from lens_domain.entities import Url
from lens_domain.errors import HostMismatch, InvalidInterval
from lens_domain.ids import CategoryId, DomainId, UrlId

__all__ = [
    "CreateUrlUseCase",
    "DeleteUrlUseCase",
    "GetUrlUseCase",
    "ListUrlsUseCase",
    "UpdateUrlUseCase",
]


class CreateUrlUseCase(UseCase[CreateUrlInput, UrlDto]):
    """Create a new tracked :class:`Url`."""

    async def run(
        self,
        input_dto: CreateUrlInput,
        uow: UnitOfWork,
        *,
        global_min_interval: int = 300,
    ) -> UrlDto:
        domain = await uow.domains.get(input_dto.domain_id)
        if domain is None:
            raise NotFoundError(f"domain not found: {input_dto.domain_id!s}")
        if input_dto.category_id is not None:
            category = await uow.categories.get(input_dto.category_id)
            if category is None:
                raise NotFoundError(
                    f"category not found: {input_dto.category_id!s}",
                )
        existing = await uow.urls.get_by_address(
            input_dto.domain_id,
            input_dto.address,
        )
        if existing is not None:
            raise ConflictError(
                f"url with address {input_dto.address!r} already exists in domain",
                details={"address": input_dto.address},
            )
        try:
            entity = Url.create(
                id=UrlId(uow.new_id()),
                domain_id=DomainId(input_dto.domain_id),
                address=input_dto.address,
                interval_seconds=input_dto.interval_seconds,
                domain_host=domain.host,
                category_id=CategoryId(input_dto.category_id) if input_dto.category_id else None,
                enabled=input_dto.enabled,
                global_min_interval=global_min_interval,
                now=uow.now(),
            )
        except HostMismatch as exc:
            raise ConflictError(str(exc), details={"host": str(exc)}) from exc
        except InvalidInterval as exc:
            raise ValidationFailed(str(exc)) from exc
        await uow.urls.add(entity)
        await uow.flush()
        return url_to_dto(entity)


class GetUrlUseCase(UseCase[UUID, UrlDto]):
    """Fetch a single :class:`Url` by id."""

    async def run(self, url_id: UUID, uow: UnitOfWork) -> UrlDto:
        entity = await uow.urls.get(url_id)
        if entity is None:
            raise NotFoundError(f"url not found: {url_id!s}")
        return url_to_dto(entity)


class ListUrlsUseCase(UseCase[dict[str, Any], ListResult[UrlDto]]):
    """List urls with optional filters and pagination."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ListResult[UrlDto]:
        entities, next_cursor = await uow.urls.list(
            domain_id=params.get("domain_id"),
            category_id=params.get("category_id"),
            status=params.get("status"),
            enabled=params.get("enabled"),
            search=params.get("search"),
            cursor=params.get("cursor"),
            limit=params.get("limit", 50),
        )
        return ListResult[UrlDto](
            items=[url_to_dto(u) for u in entities],
            next_cursor=next_cursor,
        )


class UpdateUrlUseCase(UseCase[dict[str, Any], UrlDto]):
    """Replace mutable fields on a :class:`Url`."""

    async def run(
        self,
        params: dict[str, Any],
        uow: UnitOfWork,
        *,
        global_min_interval: int = 300,
    ) -> UrlDto:
        url_id: UUID = params["id"]
        input_dto: UpdateUrlInput = params["input"]
        entity = await uow.urls.get(url_id)
        if entity is None:
            raise NotFoundError(f"url not found: {url_id!s}")
        try:
            entity.update(
                enabled=input_dto.enabled,
                interval_seconds=input_dto.interval_seconds,
                global_min_interval=global_min_interval,
                now=uow.now(),
            )
        except InvalidInterval as exc:
            raise ValidationFailed(str(exc)) from exc
        await uow.urls.update(entity)
        await uow.flush()
        return url_to_dto(entity)


class DeleteUrlUseCase(UseCase[UUID, None]):
    """Delete a :class:`Url`."""

    async def run(self, url_id: UUID, uow: UnitOfWork) -> None:
        existing = await uow.urls.get(url_id)
        if existing is None:
            raise NotFoundError(f"url not found: {url_id!s}")
        await uow.urls.delete(url_id)
