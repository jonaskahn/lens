"""Import and export use cases for ``SetupDto`` bundles.

Imports support a conflict policy:
- ``skip`` (default): leave existing rows untouched.
- ``merge``: update provided fields on existing rows.
- ``replace``: delete the existing URL and re-create it.

Exports produce a :class:`SetupDto` (or a full export) for one or all
domains. Secrets (channel apprise URLs) are never exported.
"""

from __future__ import annotations

from typing import Any

from lens_application.dto import (
    ConflictPolicy,
    ExportResult,
    ImportResult,
    SetupCategory,
    SetupDomain,
    SetupDto,
    SetupUrl,
)
from lens_application.errors import ConflictError, NotFoundError, ValidationFailed
from lens_application.ports import UnitOfWork
from lens_application.use_cases._base import UseCase
from lens_application.use_cases._mapping import (
    channel_binding_to_dto,
    channel_to_dto,
)
from lens_domain.entities import Category, Channel, ChannelBinding, Domain, Url
from lens_domain.enums import BindingScope, ChannelKind
from lens_domain.ids import CategoryId, DomainId, UrlId

__all__ = [
    "ExportSetupUseCase",
    "ImportSetupUseCase",
]


class ImportSetupUseCase(UseCase[dict[str, Any], ImportResult]):
    """Import a :class:`SetupDto` with a configurable conflict policy.

    Input format::

        {
            "setup": SetupDto(...),
            "on_conflict": ConflictPolicy.SKIP | MERGE | REPLACE,
            "global_min_interval": 300,
        }
    """

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ImportResult:
        setup: SetupDto = params["setup"]
        policy: ConflictPolicy = params.get("on_conflict", ConflictPolicy.SKIP)
        global_min_interval: int = params.get("global_min_interval", 300)
        created = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        for setup_domain in setup.domains:
            try:
                c, u = await self._import_domain(
                    uow,
                    setup_domain,
                    policy,
                    global_min_interval,
                )
                created += c
                updated += u
            except (ConflictError, ValidationFailed) as exc:
                errors.append(f"{setup_domain.host}: {exc}")

        for channel in setup.channels:
            existing = await uow.channels.get_by_name(channel.name)
            if existing is not None:
                skipped += 1
                continue
            entity = Channel.create(
                id=uow.new_id(),
                name=channel.name,
                kind=ChannelKind(channel.kind),
                apprise_url="",  # secrets not re-imported
                enabled=channel.enabled,
                now=uow.now(),
            )
            await uow.channels.add(entity)
            created += 1

        for binding in setup.bindings:
            binding_entity = ChannelBinding.create(
                id=uow.new_id(),
                channel_id=binding.channel_id,
                scope=BindingScope(binding.scope),
                scope_id=binding.scope_id,
                on_change=binding.on_change,
                on_error=binding.on_error,
                on_no_change=binding.on_no_change,
                now=uow.now(),
            )
            await uow.channel_bindings.add(binding_entity)
            created += 1

        await uow.flush()
        return ImportResult(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )

    async def _import_domain(
        self,
        uow: UnitOfWork,
        setup_domain: SetupDomain,
        policy: ConflictPolicy,
        global_min_interval: int,
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        existing = await uow.domains.get_by_host(setup_domain.host)
        if existing is not None and policy == ConflictPolicy.SKIP:
            return 0, 0
        if existing is None:
            entity = Domain.create(
                id=DomainId(uow.new_id()),
                host=setup_domain.host,
                display_name=setup_domain.display_name,
                enabled=setup_domain.enabled,
                now=uow.now(),
            )
            await uow.domains.add(entity)
            await uow.flush()
            existing = entity
            created += 1
        elif policy in (ConflictPolicy.MERGE, ConflictPolicy.REPLACE):
            existing.update(
                display_name=setup_domain.display_name,
                enabled=setup_domain.enabled,
                now=uow.now(),
            )
            await uow.domains.update(existing)
            updated += 1

        for setup_category in setup_domain.categories:
            created_c, updated_c = await self._import_category(
                uow,
                existing,
                setup_category,
                policy,
                global_min_interval,
            )
            created += created_c
            updated += updated_c
        return created, updated

    async def _import_category(
        self,
        uow: UnitOfWork,
        domain: Domain,
        setup_category: SetupCategory,
        policy: ConflictPolicy,
        global_min_interval: int,
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        existing_cat = await uow.categories.get_by_name(domain.id, setup_category.name)
        if existing_cat is not None and policy == ConflictPolicy.SKIP:
            return 0, 0
        if existing_cat is None:
            existing_cat = Category.create(
                id=CategoryId(uow.new_id()),
                domain_id=domain.id_vo,
                name=setup_category.name,
                description=setup_category.description,
                now=uow.now(),
            )
            await uow.categories.add(existing_cat)
            await uow.flush()
            created += 1
        elif policy in (ConflictPolicy.MERGE, ConflictPolicy.REPLACE):
            existing_cat.update(
                name=setup_category.name,
                description=setup_category.description,
                now=uow.now(),
            )
            await uow.categories.update(existing_cat)
            updated += 1
        for setup_url in setup_category.urls:
            created_u, updated_u = await self._import_url(
                uow,
                domain,
                existing_cat,
                setup_url,
                policy,
                global_min_interval,
            )
            created += created_u
            updated += updated_u
        return created, updated

    async def _import_url(
        self,
        uow: UnitOfWork,
        domain: Domain,
        category: Category,
        setup_url: SetupUrl,
        policy: ConflictPolicy,
        global_min_interval: int,
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        existing = await uow.urls.get_by_address(domain.id, setup_url.address)
        if existing is not None and policy == ConflictPolicy.SKIP:
            return 0, 0
        if existing is not None and policy == ConflictPolicy.REPLACE:
            await uow.urls.delete(existing.id)
            existing = None
        if existing is None:
            new = Url.create(
                id=UrlId(uow.new_id()),
                domain_id=domain.id_vo,
                address=setup_url.address,
                interval_seconds=setup_url.interval_seconds,
                domain_host=domain.host,
                category_id=category.id_vo,
                enabled=setup_url.enabled,
                global_min_interval=global_min_interval,
                now=uow.now(),
            )
            await uow.urls.add(new)
            created += 1
        else:
            existing.update(
                enabled=setup_url.enabled,
                interval_seconds=setup_url.interval_seconds,
                global_min_interval=global_min_interval,
                now=uow.now(),
            )
            await uow.urls.update(existing)
            updated += 1
        return created, updated


class ExportSetupUseCase(UseCase[dict[str, Any], ExportResult]):
    """Export a :class:`SetupDto` for one or all domains.

    Input format::

        {"domain_host": str | None}

    Secrets (channel apprise URLs) are never exported; channels are included
    for reference but with ``apprise_url`` empty.
    """

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ExportResult:
        domain_host: str | None = params.get("domain_host")
        if domain_host is not None:
            domain = await uow.domains.get_by_host(domain_host)
            if domain is None:
                raise NotFoundError(f"domain not found: {domain_host!r}")
            domains = [domain]
        else:
            domains, _ = await uow.domains.list(limit=10_000)

        setup_domains: list[SetupDomain] = []
        for domain in domains:
            categories, _ = await uow.categories.list_by_domain(
                domain_id=domain.id,
                limit=10_000,
            )
            setup_categories: list[SetupCategory] = []
            for category in categories:
                urls: list[Url] = await uow.urls.list_by_category(category.id)
                setup_categories.append(
                    SetupCategory(
                        name=category.name,
                        description=category.description,
                        crawl_config=None,
                        diff_config=None,
                        routing=None,
                        urls=[
                            SetupUrl(
                                address=u.address.value,
                                interval_seconds=u.interval.seconds,
                                enabled=u.enabled,
                                crawl_config=None,
                                diff_config=None,
                                routing=None,
                            )
                            for u in urls
                        ],
                    ),
                )
            setup_domains.append(
                SetupDomain(
                    host=domain.host.value,
                    display_name=domain.display_name,
                    enabled=domain.enabled,
                    politeness=None,
                    default_crawl_config=None,
                    default_diff_config=None,
                    default_routing=None,
                    categories=setup_categories,
                ),
            )

        channels, _ = await uow.channels.list(limit=10_000)
        bindings, _ = await uow.channel_bindings.list(limit=10_000)

        return ExportResult(
            setup=SetupDto(
                version=1,
                domains=setup_domains,
                channels=[channel_to_dto(c, has_secret=False) for c in channels],
                bindings=[channel_binding_to_dto(b) for b in bindings],
            ),
            exported_at=uow.now(),
        )
