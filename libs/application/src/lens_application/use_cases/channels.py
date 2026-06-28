"""Channel and ChannelBinding CRUD use cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lens_application.dto import (
    ChannelBindingDto,
    ChannelDto,
    CreateChannelBindingInput,
    CreateChannelInput,
    ListResult,
    UpdateChannelBindingInput,
    UpdateChannelInput,
)
from lens_application.errors import NotFoundError, ValidationFailed
from lens_application.ports import UnitOfWork
from lens_application.use_cases._base import UseCase
from lens_application.use_cases._mapping import channel_binding_to_dto, channel_to_dto
from lens_domain.entities import Channel, ChannelBinding
from lens_domain.enums import BindingScope, ChannelKind
from lens_domain.errors import InvalidScope

__all__ = [
    "CreateChannelBindingUseCase",
    "CreateChannelUseCase",
    "DeleteChannelBindingUseCase",
    "DeleteChannelUseCase",
    "GetChannelBindingUseCase",
    "GetChannelUseCase",
    "ListChannelBindingsUseCase",
    "ListChannelsUseCase",
    "UpdateChannelBindingUseCase",
    "UpdateChannelUseCase",
]


class CreateChannelUseCase(UseCase[CreateChannelInput, ChannelDto]):
    """Create a new :class:`Channel`."""

    async def run(self, input_dto: CreateChannelInput, uow: UnitOfWork) -> ChannelDto:
        entity = Channel.create(
            id=uow.new_id(),
            name=input_dto.name,
            kind=ChannelKind(input_dto.kind),
            apprise_url=input_dto.apprise_url,
            enabled=input_dto.enabled,
            now=uow.now(),
        )
        await uow.channels.add(entity)
        await uow.flush()
        return channel_to_dto(entity, has_secret=True)


class GetChannelUseCase(UseCase[UUID, ChannelDto]):
    """Fetch a single :class:`Channel` by id."""

    async def run(self, channel_id: UUID, uow: UnitOfWork) -> ChannelDto:
        entity = await uow.channels.get(channel_id)
        if entity is None:
            raise NotFoundError(f"channel not found: {channel_id!s}")
        return channel_to_dto(entity, has_secret=True)


class ListChannelsUseCase(UseCase[dict[str, Any], ListResult[ChannelDto]]):
    """List channels with pagination."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ListResult[ChannelDto]:
        entities, next_cursor = await uow.channels.list(
            cursor=params.get("cursor"),
            limit=params.get("limit", 50),
        )
        return ListResult[ChannelDto](
            items=[channel_to_dto(c, has_secret=True) for c in entities],
            next_cursor=next_cursor,
        )


class UpdateChannelUseCase(UseCase[dict[str, Any], ChannelDto]):
    """Replace mutable fields on a :class:`Channel`."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ChannelDto:
        channel_id: UUID = params["id"]
        input_dto: UpdateChannelInput = params["input"]
        entity = await uow.channels.get(channel_id)
        if entity is None:
            raise NotFoundError(f"channel not found: {channel_id!s}")
        entity.update(
            name=input_dto.name,
            kind=ChannelKind(input_dto.kind) if input_dto.kind else None,
            apprise_url=input_dto.apprise_url,
            enabled=input_dto.enabled,
            now=uow.now(),
        )
        await uow.channels.update(entity)
        await uow.flush()
        return channel_to_dto(entity, has_secret=True)


class DeleteChannelUseCase(UseCase[UUID, None]):
    """Delete a :class:`Channel` (cascades to bindings)."""

    async def run(self, channel_id: UUID, uow: UnitOfWork) -> None:
        existing = await uow.channels.get(channel_id)
        if existing is None:
            raise NotFoundError(f"channel not found: {channel_id!s}")
        await uow.channels.delete(channel_id)


class CreateChannelBindingUseCase(UseCase[CreateChannelBindingInput, ChannelBindingDto]):
    """Bind a :class:`Channel` to a scope with trigger flags."""

    async def run(
        self,
        input_dto: CreateChannelBindingInput,
        uow: UnitOfWork,
    ) -> ChannelBindingDto:
        try:
            entity = ChannelBinding.create(
                id=uow.new_id(),
                channel_id=input_dto.channel_id,
                scope=BindingScope(input_dto.scope),
                scope_id=input_dto.scope_id,
                on_change=input_dto.on_change,
                on_error=input_dto.on_error,
                on_no_change=input_dto.on_no_change,
                now=uow.now(),
            )
        except InvalidScope as exc:
            raise ValidationFailed(str(exc)) from exc
        await uow.channel_bindings.add(entity)
        await uow.flush()
        return channel_binding_to_dto(entity)


class GetChannelBindingUseCase(UseCase[UUID, ChannelBindingDto]):
    """Fetch a single :class:`ChannelBinding` by id."""

    async def run(self, binding_id: UUID, uow: UnitOfWork) -> ChannelBindingDto:
        entity = await uow.channel_bindings.get(binding_id)
        if entity is None:
            raise NotFoundError(f"channel binding not found: {binding_id!s}")
        return channel_binding_to_dto(entity)


class ListChannelBindingsUseCase(UseCase[dict[str, Any], ListResult[ChannelBindingDto]]):
    """List channel bindings with optional filters and pagination."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ListResult[ChannelBindingDto]:
        entities, next_cursor = await uow.channel_bindings.list(
            scope=params.get("scope"),
            scope_id=params.get("scope_id"),
            channel_id=params.get("channel_id"),
            cursor=params.get("cursor"),
            limit=params.get("limit", 50),
        )
        return ListResult[ChannelBindingDto](
            items=[channel_binding_to_dto(b) for b in entities],
            next_cursor=next_cursor,
        )


class UpdateChannelBindingUseCase(UseCase[dict[str, Any], ChannelBindingDto]):
    """Replace trigger flags on a :class:`ChannelBinding`."""

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ChannelBindingDto:
        binding_id: UUID = params["id"]
        input_dto: UpdateChannelBindingInput = params["input"]
        entity = await uow.channel_bindings.get(binding_id)
        if entity is None:
            raise NotFoundError(f"channel binding not found: {binding_id!s}")
        entity.update(
            on_change=input_dto.on_change,
            on_error=input_dto.on_error,
            on_no_change=input_dto.on_no_change,
        )
        await uow.channel_bindings.update(entity)
        await uow.flush()
        return channel_binding_to_dto(entity)


class DeleteChannelBindingUseCase(UseCase[UUID, None]):
    """Delete a :class:`ChannelBinding`."""

    async def run(self, binding_id: UUID, uow: UnitOfWork) -> None:
        existing = await uow.channel_bindings.get(binding_id)
        if existing is None:
            raise NotFoundError(f"channel binding not found: {binding_id!s}")
        await uow.channel_bindings.delete(binding_id)
