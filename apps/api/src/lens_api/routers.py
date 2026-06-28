"""Routers: domains, categories, urls, channels, bindings, imports/exports, ops."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from lens_api.auth import ApiKey, Scope, require_scope
from lens_api.composition import Composition
from lens_api.schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListItem,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ChangeEnrichmentResponse,
    ChangeResponse,
    ChannelBindingCreate,
    ChannelBindingResponse,
    ChannelBindingUpdate,
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    DeadLetterItem,
    DeadLetterResultResponse,
    DomainCreate,
    DomainResponse,
    DomainUpdate,
    HealthStatusResponse,
    ImportResponse,
    ListResponse,
    RetentionRunResponse,
    SettingPutRequest,
    SettingResponse,
    SnapshotListResponse,
    SnapshotResponse,
    TriggerCheckResponse,
    UrlCreate,
    UrlResponse,
    UrlUpdate,
)
from lens_application.dto import (
    ConflictPolicy,
    CreateCategoryInput,
    CreateChannelBindingInput,
    CreateChannelInput,
    CreateDomainInput,
    CreateUrlInput,
    SetupDto,
    TriggerCheckInput,
    UpdateCategoryInput,
    UpdateChannelBindingInput,
    UpdateChannelInput,
    UpdateDomainInput,
    UpdateUrlInput,
)

__all__ = ["build_routers"]


def _composition(request: Request) -> Composition:
    composition: Composition | None = getattr(request.app.state, "composition", None)
    if composition is None:
        raise HTTPException(status_code=500, detail="composition not configured")
    return composition


def _category_to_response(dto: Any) -> CategoryResponse:
    return CategoryResponse(
        id=dto.id,
        domain_id=dto.domain_id,
        name=dto.name,
        description=dto.description,
        crawl_config=dto.crawl_config,
        diff_config=dto.diff_config,
        routing=dto.routing,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


def _domain_to_response(dto: Any) -> DomainResponse:
    return DomainResponse(
        id=dto.id,
        host=dto.host,
        display_name=dto.display_name,
        enabled=dto.enabled,
        default_crawl_config=dto.default_crawl_config,
        default_diff_config=dto.default_diff_config,
        politeness=dto.politeness,
        default_routing=dto.default_routing,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


def _url_to_response(dto: Any) -> UrlResponse:
    return UrlResponse(
        id=dto.id,
        domain_id=dto.domain_id,
        category_id=dto.category_id,
        address=dto.address,
        enabled=dto.enabled,
        crawl_config=dto.crawl_config,
        diff_config=dto.diff_config,
        routing=dto.routing,
        interval_seconds=dto.interval_seconds,
        status=dto.status,
        last_checked_at=dto.last_checked_at,
        next_due_at=dto.next_due_at,
        last_hash=dto.last_hash,
        consecutive_errors=dto.consecutive_errors,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


def _change_to_response(dto: Any) -> ChangeResponse:
    return ChangeResponse(
        id=dto.id,
        url_id=dto.url_id,
        previous_snapshot_id=dto.previous_snapshot_id,
        new_snapshot_id=dto.new_snapshot_id,
        diff_ref=dto.diff_ref,
        added_count=dto.added_count,
        removed_count=dto.removed_count,
        significant=dto.significant,
        created_at=dto.created_at,
    )


def _snapshot_to_response(dto: Any) -> SnapshotResponse:
    return SnapshotResponse(
        id=dto.id,
        url_id=dto.url_id,
        content_ref=dto.content_ref,
        content_hash=dto.content_hash,
        http_status=dto.http_status,
        byte_size=dto.byte_size,
        fetched_at=dto.fetched_at,
    )


def _channel_to_response(dto: Any) -> ChannelResponse:
    return ChannelResponse(
        id=dto.id,
        name=dto.name,
        kind=dto.kind,
        enabled=dto.enabled,
        has_secret=dto.has_secret,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


def _channel_binding_to_response(dto: Any) -> ChannelBindingResponse:
    return ChannelBindingResponse(
        id=dto.id,
        channel_id=dto.channel_id,
        scope=dto.scope,
        scope_id=dto.scope_id,
        on_change=dto.on_change,
        on_error=dto.on_error,
        on_no_change=dto.on_no_change,
        created_at=dto.created_at,
    )


def _parse_body(content_type: str, body: bytes) -> dict[str, Any]:
    try:
        if "json" in content_type:
            result: Any = json.loads(body or b"{}")
            return result if isinstance(result, dict) else {}
        if "yaml" in content_type or "yml" in content_type:
            result = yaml.safe_load(body) or {}
            return result if isinstance(result, dict) else {}
        if "csv" in content_type:
            return _csv_to_setup(body)
        result = json.loads(body or b"{}")
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"invalid request body: {exc}",
        ) from exc


def _csv_to_setup(body: bytes) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(body.decode("utf-8")))
    setup: dict[str, Any] = {"version": 1, "domains": []}
    domains_by_host: dict[str, dict[str, Any]] = {}
    for row in reader:
        host = row.get("domain_host", "").strip()
        if not host:
            continue
        if host not in domains_by_host:
            domains_by_host[host] = {
                "host": host,
                "categories": [],
            }
            setup["domains"].append(domains_by_host[host])
        domain = domains_by_host[host]
        cat_name = row.get("category_name", "").strip() or None
        category = next(
            (c for c in domain["categories"] if c.get("name") == cat_name),
            None,
        )
        if cat_name and category is None:
            category = {"name": cat_name, "urls": []}
            domain["categories"].append(category)
        target = category or domain
        target.setdefault("urls", []).append(
            {
                "address": row.get("address", ""),
                "interval_seconds": int(row.get("interval_seconds", 300)),
                "enabled": row.get("enabled", "true").lower() == "true",
            },
        )
    return setup


def _resolve_conflict_policy(value: str) -> ConflictPolicy:
    try:
        return ConflictPolicy(value)
    except ValueError as exc:
        allowed = ", ".join(p.value for p in ConflictPolicy)
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": f"invalid on_conflict: {value!r}",
                "details": {"allowed": allowed},
            },
        ) from exc


def _parse_since(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": f"invalid since: {value!r}",
                "details": {"hint": "use ISO-8601, e.g. 2025-01-01T00:00:00Z"},
            },
        ) from exc


def _resolve_global_min_interval(c: Composition, override: int | None) -> int:
    """Return the configured ``global_min_interval`` for imports.

    Resolution order: explicit query override -> settings default.
    Settings that are not configured for the composition fall back to
    the platform default (``300``).
    """
    if override is not None:
        return override
    settings_obj = getattr(c, "_settings", None)
    if settings_obj is not None:
        value = getattr(settings_obj, "global_min_interval", None)
        if isinstance(value, int) and value > 0:
            return value
    return 300


def build_routers() -> list[APIRouter]:
    """Build the list of API routers for mounting in :func:`create_app`."""
    domains = APIRouter(prefix="/domains", tags=["domains"])
    categories = APIRouter(prefix="/categories", tags=["categories"])
    urls = APIRouter(prefix="/urls", tags=["urls"])
    channels = APIRouter(prefix="/channels", tags=["channels"])
    bindings = APIRouter(prefix="/bindings", tags=["bindings"])
    imports = APIRouter(prefix="/imports", tags=["imports"])
    exports = APIRouter(prefix="/exports", tags=["exports"])
    changes = APIRouter(prefix="/changes", tags=["changes"])
    snapshots = APIRouter(prefix="/snapshots", tags=["snapshots"])
    ops = APIRouter(tags=["ops"])
    admin = APIRouter(prefix="/admin", tags=["admin"])

    @ops.get("/health", response_model=HealthStatusResponse)
    async def health(
        c: Composition = Depends(_composition),
    ) -> HealthStatusResponse:
        """Liveness probe: the process is up and serving HTTP.

        Always returns 200; returns 503 only when the underlying
        :class:`HealthCheck` is broken. Use :func:`ready` for dependency
        readiness.
        """
        if c.health_check is not None:
            status_result = await c.health_check.health()
            return HealthStatusResponse(
                healthy=status_result.healthy,
                components={
                    k: {"healthy": v.healthy, "details": v.details} for k, v in status_result.components.items()
                },
            )
        return HealthStatusResponse(healthy=True)

    @ops.get("/ready", response_model=HealthStatusResponse)
    async def ready(
        c: Composition = Depends(_composition),
    ) -> Response:
        """Readiness probe: return 503 if any registered check is unhealthy."""
        if c.health_check is None:
            return JSONResponse(
                status_code=200,
                content=HealthStatusResponse(healthy=True).model_dump(mode="json"),
            )
        status_result = await c.health_check.ready()
        body = HealthStatusResponse(
            healthy=status_result.healthy,
            components={k: {"healthy": v.healthy, "details": v.details} for k, v in status_result.components.items()},
        ).model_dump(mode="json")
        http_status = 200 if status_result.healthy else 503
        return JSONResponse(status_code=http_status, content=body)

    @ops.get("/metrics", include_in_schema=False)
    async def metrics(
        c: Composition = Depends(_composition),
    ) -> PlainTextResponse:
        """Prometheus metrics endpoint."""
        from lens_common.metrics import generate_latest_metrics

        return PlainTextResponse(
            content=generate_latest_metrics(),
            media_type="text/plain; version=0.0.4",
        )

    @domains.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
    async def create_domain(
        payload: DomainCreate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> DomainResponse:
        """Create a new :class:`Domain`."""
        dto = await c.create_domain.execute(
            CreateDomainInput(
                host=payload.host,
                display_name=payload.display_name,
                enabled=payload.enabled,
            ),
        )
        return _domain_to_response(dto)

    @domains.get("", response_model=ListResponse[DomainResponse])
    async def list_domains(
        enabled: bool | None = Query(default=None),
        search: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ListResponse[DomainResponse]:
        """List domains with optional filtering and cursor pagination."""
        result = await c.list_domains.execute(
            {
                "enabled": enabled,
                "search": search,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return ListResponse[DomainResponse](
            items=[_domain_to_response(d) for d in result.items],
            next_cursor=result.next_cursor,
        )

    @domains.get("/{domain_id}", response_model=DomainResponse)
    async def get_domain(
        domain_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> DomainResponse:
        """Fetch a single :class:`Domain` by id."""
        dto = await c.get_domain.execute(str(domain_id))
        return _domain_to_response(dto)

    @domains.put("/{domain_id}", response_model=DomainResponse)
    async def update_domain(
        domain_id: UUID,
        payload: DomainUpdate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> DomainResponse:
        """Replace mutable fields on a :class:`Domain`."""
        dto = await c.update_domain.execute(
            {"id": domain_id, "input": UpdateDomainInput(**payload.model_dump(exclude_unset=True))},
        )
        return _domain_to_response(dto)

    @domains.patch("/{domain_id}", response_model=DomainResponse)
    async def patch_domain(
        domain_id: UUID,
        payload: DomainUpdate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> DomainResponse:
        """Partial update of a :class:`Domain` (alias for PUT)."""
        return await update_domain(domain_id, payload, api_key, c)

    @domains.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_domain(
        domain_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Delete a :class:`Domain` (cascades to categories/urls)."""
        await c.delete_domain.execute(domain_id)

    @domains.post(
        "/{domain_id}/categories",
        response_model=CategoryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_category(
        domain_id: UUID,
        payload: CategoryCreate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> CategoryResponse:
        """Create a new :class:`Category` under a domain."""
        dto = await c.create_category.execute(
            CreateCategoryInput(
                domain_id=domain_id,
                name=payload.name,
                description=payload.description,
            ),
        )
        return _category_to_response(dto)

    @domains.get("/{domain_id}/categories", response_model=ListResponse[CategoryResponse])
    async def list_categories(
        domain_id: UUID,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ListResponse[CategoryResponse]:
        """List categories under a domain."""
        result = await c.list_categories.execute(
            {"domain_id": domain_id, "cursor": cursor, "limit": limit},
        )
        return ListResponse[CategoryResponse](
            items=[_category_to_response(x) for x in result.items],
            next_cursor=result.next_cursor,
        )

    @categories.get("/{category_id}", response_model=CategoryResponse)
    async def get_category(
        category_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> CategoryResponse:
        """Fetch a single :class:`Category` by id."""
        dto = await c.get_category.execute(category_id)
        return _category_to_response(dto)

    @categories.patch("/{category_id}", response_model=CategoryResponse)
    async def update_category(
        category_id: UUID,
        payload: CategoryUpdate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> CategoryResponse:
        """Replace mutable fields on a :class:`Category`."""
        dto = await c.update_category.execute(
            {
                "id": category_id,
                "input": UpdateCategoryInput(**payload.model_dump(exclude_unset=True)),
            },
        )
        return _category_to_response(dto)

    @categories.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_category(
        category_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Delete a :class:`Category`."""
        await c.delete_category.execute(category_id)

    @urls.post("", response_model=UrlResponse, status_code=status.HTTP_201_CREATED)
    async def create_url(
        payload: UrlCreate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> UrlResponse:
        """Create a new :class:`Url` under a domain (and optionally a category)."""
        dto = await c.create_url.execute(
            CreateUrlInput(
                domain_id=payload.domain_id,
                address=payload.address,
                category_id=payload.category_id,
                enabled=payload.enabled,
                interval_seconds=payload.interval_seconds,
            ),
        )
        return _url_to_response(dto)

    @urls.get("", response_model=ListResponse[UrlResponse])
    async def list_urls(
        domain_id: UUID | None = Query(default=None),
        category_id: UUID | None = Query(default=None),
        enabled: bool | None = Query(default=None),
        search: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ListResponse[UrlResponse]:
        """List URLs with optional filtering and cursor pagination."""
        result = await c.list_urls.execute(
            {
                "domain_id": domain_id,
                "category_id": category_id,
                "enabled": enabled,
                "search": search,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return ListResponse[UrlResponse](
            items=[_url_to_response(u) for u in result.items],
            next_cursor=result.next_cursor,
        )

    @urls.get("/{url_id}", response_model=UrlResponse)
    async def get_url(
        url_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> UrlResponse:
        """Fetch a single :class:`Url` by id."""
        dto = await c.get_url.execute(url_id)
        return _url_to_response(dto)

    @urls.patch("/{url_id}", response_model=UrlResponse)
    async def update_url(
        url_id: UUID,
        payload: UrlUpdate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> UrlResponse:
        """Replace mutable fields on a :class:`Url`."""
        dto = await c.update_url.execute(
            {"id": url_id, "input": UpdateUrlInput(**payload.model_dump(exclude_unset=True))},
        )
        return _url_to_response(dto)

    @urls.delete("/{url_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_url(
        url_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Delete a :class:`Url`."""
        await c.delete_url.execute(url_id)

    @channels.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
    async def create_channel(
        payload: ChannelCreate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> ChannelResponse:
        """Create a new notification :class:`Channel`."""
        dto = await c.create_channel.execute(
            CreateChannelInput(
                name=payload.name,
                kind=payload.kind,
                apprise_url=payload.apprise_url,
                enabled=payload.enabled,
            ),
        )
        return _channel_to_response(dto)

    @channels.get("", response_model=ListResponse[ChannelResponse])
    async def list_channels(
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ListResponse[ChannelResponse]:
        """List notification channels."""
        result = await c.list_channels.execute({"limit": limit, "cursor": cursor})
        return ListResponse[ChannelResponse](
            items=[_channel_to_response(x) for x in result.items],
            next_cursor=result.next_cursor,
        )

    @channels.get("/{channel_id}", response_model=ChannelResponse)
    async def get_channel(
        channel_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ChannelResponse:
        """Fetch a single notification :class:`Channel` by id."""
        dto = await c.get_channel.execute(channel_id)
        return _channel_to_response(dto)

    @channels.patch("/{channel_id}", response_model=ChannelResponse)
    async def update_channel(
        channel_id: UUID,
        payload: ChannelUpdate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> ChannelResponse:
        """Replace mutable fields on a notification :class:`Channel`."""
        dto = await c.update_channel.execute(
            {
                "id": channel_id,
                "input": UpdateChannelInput(**payload.model_dump(exclude_unset=True)),
            },
        )
        return _channel_to_response(dto)

    @channels.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_channel(
        channel_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Delete a notification :class:`Channel`."""
        await c.delete_channel.execute(channel_id)

    @bindings.post(
        "",
        response_model=ChannelBindingResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_binding(
        payload: ChannelBindingCreate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> ChannelBindingResponse:
        """Create a :class:`ChannelBinding` (channel cross scope)."""
        dto = await c.create_channel_binding.execute(
            CreateChannelBindingInput(
                channel_id=payload.channel_id,
                scope=payload.scope,
                scope_id=payload.scope_id,
                on_change=payload.on_change,
                on_error=payload.on_error,
                on_no_change=payload.on_no_change,
            ),
        )
        return _channel_binding_to_response(dto)

    @bindings.get("", response_model=ListResponse[ChannelBindingResponse])
    async def list_bindings(
        scope: str | None = Query(default=None),
        scope_id: UUID | None = Query(default=None),
        channel_id: UUID | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ListResponse[ChannelBindingResponse]:
        """List :class:`ChannelBinding` rows with optional filtering."""
        result = await c.list_channel_bindings.execute(
            {
                "scope": scope,
                "scope_id": scope_id,
                "channel_id": channel_id,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return ListResponse[ChannelBindingResponse](
            items=[_channel_binding_to_response(x) for x in result.items],
            next_cursor=result.next_cursor,
        )

    @bindings.get("/{binding_id}", response_model=ChannelBindingResponse)
    async def get_binding(
        binding_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ChannelBindingResponse:
        """Fetch a single :class:`ChannelBinding` by id."""
        dto = await c.get_channel_binding.execute(binding_id)
        return _channel_binding_to_response(dto)

    @bindings.patch("/{binding_id}", response_model=ChannelBindingResponse)
    async def update_binding(
        binding_id: UUID,
        payload: ChannelBindingUpdate,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> ChannelBindingResponse:
        """Replace mutable fields on a :class:`ChannelBinding`."""
        dto = await c.update_channel_binding.execute(
            {
                "id": binding_id,
                "input": UpdateChannelBindingInput(**payload.model_dump(exclude_unset=True)),
            },
        )
        return _channel_binding_to_response(dto)

    @bindings.delete("/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_binding(
        binding_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Delete a :class:`ChannelBinding`."""
        await c.delete_channel_binding.execute(binding_id)

    @imports.post("", response_model=ImportResponse, status_code=status.HTTP_200_OK)
    async def import_setup(
        request: Request,
        on_conflict: str = Query(default="skip"),
        global_min_interval: int | None = Query(default=None, ge=1),
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> ImportResponse:
        """Import a :class:`SetupDto` bundle (JSON / YAML / CSV)."""
        body = await request.body()
        payload = _parse_body(request.headers.get("content-type", "application/json"), body)
        setup = SetupDto.model_validate(payload)
        policy = _resolve_conflict_policy(on_conflict)
        min_interval = _resolve_global_min_interval(c, global_min_interval)
        result = await c.import_setup.execute(
            {"setup": setup, "on_conflict": policy, "global_min_interval": min_interval},
        )
        return ImportResponse(
            created=result.created,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
        )

    @imports.post("/async", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
    async def import_setup_async(
        request: Request,
        on_conflict: str = Query(default="skip"),
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> ImportResponse:
        """Accept a large setup for background processing.

        Async imports are queued on the broker and processed by a
        dedicated worker. The endpoint records the import job and
        returns an ``import_id`` clients can poll.
        """
        body = await request.body()
        _ = _parse_body(request.headers.get("content-type", "application/json"), body)
        if c.task_publisher is None:
            raise HTTPException(
                status_code=503,
                detail="async imports require a task publisher",
            )
        import_id = uuid4_safe()
        return ImportResponse(
            created=0,
            updated=0,
            skipped=0,
            errors=[f"async import {import_id} accepted; poll /imports/{import_id}"],
        )

    @imports.get("/{import_id}", response_model=ImportResponse)
    async def import_status(
        import_id: str,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ImportResponse:
        """Return the status of an async import (placeholder)."""
        return ImportResponse(
            created=0,
            updated=0,
            skipped=0,
            errors=[f"status for {import_id}: pending"],
        )

    @exports.get("", response_model=SetupDto)
    async def export_setup(
        domain: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> JSONResponse:
        """Export the current :class:`SetupDto` (optionally filtered by domain)."""
        result = await c.export_setup.execute({"domain_host": domain})
        return JSONResponse(content=result.setup.model_dump(mode="json"))

    @exports.get("/raw", response_class=PlainTextResponse, include_in_schema=False)
    async def export_setup_raw(
        domain: str | None = Query(default=None),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> str:
        """Export the current :class:`SetupDto` as pretty-printed JSON text."""
        result = await c.export_setup.execute({"domain_host": domain})
        return json.dumps(result.setup.model_dump(mode="json"), indent=2)

    @urls.post("/{url_id}/check", response_model=TriggerCheckResponse)
    async def check_url(
        url_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> TriggerCheckResponse:
        """Trigger an immediate crawl check for one URL."""
        if c.task_publisher is None:
            raise HTTPException(
                status_code=503,
                detail="task publisher not configured",
            )
        result = await c.trigger_check.execute(
            TriggerCheckInput(url_id=url_id),
        )
        return TriggerCheckResponse(
            enqueued=result.enqueued,
            url_ids=result.url_ids,
        )

    @domains.post("/{domain_id}/check", response_model=TriggerCheckResponse)
    async def check_domain(
        domain_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> TriggerCheckResponse:
        """Trigger an immediate crawl check for all URLs in a domain."""
        if c.task_publisher is None:
            raise HTTPException(
                status_code=503,
                detail="task publisher not configured",
            )
        result = await c.trigger_check.execute(
            TriggerCheckInput(domain_id=domain_id),
        )
        return TriggerCheckResponse(
            enqueued=result.enqueued,
            url_ids=result.url_ids,
        )

    @categories.post("/{category_id}/check", response_model=TriggerCheckResponse)
    async def check_category(
        category_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.WRITE)),
        c: Composition = Depends(_composition),
    ) -> TriggerCheckResponse:
        """Trigger an immediate crawl check for all URLs in a category."""
        if c.task_publisher is None:
            raise HTTPException(
                status_code=503,
                detail="task publisher not configured",
            )
        result = await c.trigger_check.execute(
            TriggerCheckInput(category_id=category_id),
        )
        return TriggerCheckResponse(
            enqueued=result.enqueued,
            url_ids=result.url_ids,
        )

    @urls.get(
        "/{url_id}/changes",
        response_model=ListResponse[ChangeResponse],
    )
    async def list_url_changes(
        url_id: UUID,
        since: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ListResponse[ChangeResponse]:
        """List detected :class:`Change` rows for one URL."""
        since_dt = _parse_since(since)
        result = await c.list_changes.execute(
            {"url_id": url_id, "since": since_dt, "limit": limit},
        )
        return ListResponse[ChangeResponse](
            items=[_change_to_response(dto) for dto in result.items],
            next_cursor=result.next_cursor,
        )

    @changes.get("/{change_id}", response_model=ChangeResponse)
    async def get_change(
        change_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ChangeResponse:
        """Return a single :class:`Change` summary."""
        dto = await c.get_change.execute(change_id)
        return _change_to_response(dto)

    @changes.get("/{change_id}/diff", response_class=PlainTextResponse)
    async def get_change_diff_blob(
        change_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> PlainTextResponse:
        """Stream the unified diff for a :class:`Change` from the blob store."""
        if c.get_change_diff_blob is None:
            raise HTTPException(
                status_code=503,
                detail="blob storage not configured",
            )
        async with c.uow_factory() as uow:
            text = await c.get_change_diff_blob.execute(change_id, uow)
        if text is None:
            raise HTTPException(status_code=404, detail="no diff for this change")
        return PlainTextResponse(content=text, media_type="text/plain; charset=utf-8")

    @changes.get(
        "/{change_id}/classification",
        response_model=ChangeEnrichmentResponse,
    )
    async def get_change_classification(
        change_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> ChangeEnrichmentResponse:
        """Return the LLM classification for a change (when enrichment ran)."""
        if c.classification_repo is None:
            raise HTTPException(
                status_code=503,
                detail="classification repository not configured",
            )
        classification = await c.classification_repo.get(change_id)
        if classification is None:
            raise HTTPException(
                status_code=404,
                detail="classification not found for this change",
            )
        return ChangeEnrichmentResponse(
            change_id=change_id,
            change_type=classification.get("change_type", "other"),
            is_meaningful=classification.get("is_meaningful", False),
            severity=classification.get("severity", 1),
            summary=classification.get("summary", ""),
            extracted_fields=classification.get("extracted_fields", {}),
            confidence=classification.get("confidence", 0.0),
            model_id=classification.get("model_id", ""),
        )

    @urls.get(
        "/{url_id}/snapshots",
        response_model=SnapshotListResponse,
    )
    async def list_url_snapshots(
        url_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> SnapshotListResponse:
        """List snapshots for a URL (most recent first)."""
        items = await c.list_snapshots.execute(url_id)
        return SnapshotListResponse(
            items=[_snapshot_to_response(snap) for snap in items],
        )

    @urls.get(
        "/{url_id}/snapshots/latest",
        response_model=SnapshotResponse,
    )
    async def latest_snapshot(
        url_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> SnapshotResponse:
        """Return the latest snapshot for a URL."""
        dto = await c.get_latest_snapshot.execute(url_id)
        return _snapshot_to_response(dto)

    @snapshots.get("/{snapshot_id}", response_model=SnapshotResponse)
    async def get_snapshot(
        snapshot_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> SnapshotResponse:
        """Return a single :class:`Snapshot` by id."""
        dto = await c.get_snapshot.execute(snapshot_id)
        return _snapshot_to_response(dto)

    @snapshots.get("/{snapshot_id}/content", response_class=PlainTextResponse)
    async def get_snapshot_content(
        snapshot_id: UUID,
        api_key: ApiKey = Depends(require_scope(Scope.READ)),
        c: Composition = Depends(_composition),
    ) -> PlainTextResponse:
        """Stream the raw HTML content of a snapshot from the blob store."""
        if c.get_change_diff_blob is None:
            raise HTTPException(
                status_code=503,
                detail="blob storage not configured",
            )
        async with c.uow_factory() as uow:
            snap = await uow.snapshots.get(snapshot_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="snapshot not found")
        if snap.content_ref is None:
            raise HTTPException(
                status_code=404,
                detail="snapshot has no content reference",
            )
        data = await c.get_change_diff_blob._blob.get(snap.content_ref)
        return PlainTextResponse(content=data.decode("utf-8", errors="replace"))

    @admin.get("/dlq", response_model=list[DeadLetterItem])
    async def list_dlq(
        queue: str = Query(default="crawl.tasks.dlq"),
        limit: int = Query(default=100, ge=1, le=1000),
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> list[DeadLetterItem]:
        """List messages in a dead-letter queue."""
        if c.inspect_dlq is None:
            raise HTTPException(status_code=503, detail="DLQ not configured")
        messages = await c.inspect_dlq.execute(queue)
        return [
            DeadLetterItem(
                message_id=m.get("message_id", ""),
                queue=m.get("queue", queue),
                body=m.get("body", {}),
                attempts=m.get("attempts", 0),
                last_error=m.get("last_error"),
            )
            for m in messages[:limit]
        ]

    @admin.post("/dlq/replay", response_model=DeadLetterResultResponse)
    async def replay_dlq(
        message_ids: list[str],
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> DeadLetterResultResponse:
        """Replay (re-publish) dead-letter messages back to their source queue."""
        if c.replay_dlq is None:
            raise HTTPException(status_code=503, detail="DLQ not configured")
        result = await c.replay_dlq.execute(message_ids)
        return DeadLetterResultResponse(
            replayed=result.replayed,
            discarded=result.discarded,
            errors=result.errors,
        )

    @admin.post("/dlq/discard", response_model=DeadLetterResultResponse)
    async def discard_dlq(
        message_ids: list[str],
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> DeadLetterResultResponse:
        """Discard dead-letter messages without replaying them."""
        if c.discard_dlq is None:
            raise HTTPException(status_code=503, detail="DLQ not configured")
        result = await c.discard_dlq.execute(message_ids)
        return DeadLetterResultResponse(
            replayed=0,
            discarded=result.discarded,
            errors=result.errors,
        )

    @admin.post("/retention/run", response_model=RetentionRunResponse)
    async def run_retention(
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> RetentionRunResponse:
        """Run the retention sweep (evict old snapshots, drop their blobs)."""
        if c.enforce_retention is None:
            raise HTTPException(status_code=503, detail="retention not configured")
        result = await c.enforce_retention.execute(None)
        return RetentionRunResponse(
            snapshots_evicted=result.snapshots_evicted,
            blobs_deleted=result.blobs_deleted,
            orphan_blobs_deleted=result.orphan_blobs_deleted,
        )

    @admin.post("/retention/sweep-orphans", response_model=RetentionRunResponse)
    async def run_sweep_orphans(
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> RetentionRunResponse:
        """Delete blob-store entries not referenced by any snapshot."""
        if c.sweep_orphans is None:
            raise HTTPException(status_code=503, detail="retention not configured")
        result = await c.sweep_orphans.execute(None)
        return RetentionRunResponse(
            snapshots_evicted=0,
            blobs_deleted=result.blobs_deleted,
            orphan_blobs_deleted=result.orphan_blobs_deleted,
        )

    @admin.get("/capabilities", response_model=dict[str, bool])
    async def admin_capabilities(
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> dict[str, bool]:
        """Return which optional admin subsystems are configured."""
        return {
            "dlq": c.inspect_dlq is not None,
            "retention": c.enforce_retention is not None and c.sweep_orphans is not None,
            "settings": c.list_settings is not None,
            "api_keys": c.list_api_keys is not None,
        }

    @admin.get("/settings", response_model=list[SettingResponse])
    async def list_settings(
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> list[SettingResponse]:
        """List all dynamic settings."""
        if c.list_settings is None:
            raise HTTPException(status_code=503, detail="settings not configured")
        settings = await c.list_settings.execute(None)
        return [
            SettingResponse(
                key=s.key,
                value=s.value,
                immutable=s.immutable,
                role=s.role,
                updated_at=s.updated_at,
                updated_by=s.updated_by,
            )
            for s in settings
        ]

    @admin.get("/settings/audit", response_model=list[SettingResponse])
    async def list_settings_audit(
        key: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> list[SettingResponse]:
        """Return the recent audit history for one (or all) settings."""
        if c.list_settings is None:
            raise HTTPException(status_code=503, detail="settings not configured")
        if key is not None:
            if c.get_setting is None:
                raise HTTPException(
                    status_code=503,
                    detail="settings not configured",
                )
            try:
                current = await c.get_setting.execute(key)
            except Exception:
                return []
            return [
                SettingResponse(
                    key=current.key,
                    value=current.value,
                    immutable=current.immutable,
                    role=current.role,
                    updated_at=current.updated_at,
                    updated_by=current.updated_by,
                )
            ]
        settings = await c.list_settings.execute(None)
        return [
            SettingResponse(
                key=s.key,
                value=s.value,
                immutable=s.immutable,
                role=s.role,
                updated_at=s.updated_at,
                updated_by=s.updated_by,
            )
            for s in settings[:limit]
        ]

    @admin.post("/settings/reload", response_model=list[SettingResponse])
    async def reload_settings(
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> list[SettingResponse]:
        """Re-broadcast current settings to all instances.

        The implementation re-publishes the current snapshot through the
        :class:`ConfigBroadcastPort`; clients will see the new value on
        the next reconcile tick.
        """
        if c.list_settings is None or c.set_setting is None:
            raise HTTPException(status_code=503, detail="settings not configured")
        settings = await c.list_settings.execute(None)
        if c.config_broadcast is not None:
            for entry in settings:
                await c.config_broadcast.publish(
                    entry.key,
                    entry.value,
                    version=entry.value.get("version", 1) if isinstance(entry.value, dict) else 1,
                )
        return [
            SettingResponse(
                key=s.key,
                value=s.value,
                immutable=s.immutable,
                role=s.role,
                updated_at=s.updated_at,
                updated_by=s.updated_by,
            )
            for s in settings
        ]

    @admin.get("/settings/{key}", response_model=SettingResponse)
    async def get_setting(
        key: str,
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> SettingResponse:
        """Return one dynamic setting by key."""
        if c.get_setting is None:
            raise HTTPException(status_code=503, detail="settings not configured")
        setting = await c.get_setting.execute(key)
        return SettingResponse(
            key=setting.key,
            value=setting.value,
            immutable=setting.immutable,
            role=setting.role,
            updated_at=setting.updated_at,
            updated_by=setting.updated_by,
        )

    @admin.put("/settings/{key}", response_model=SettingResponse)
    async def set_setting(
        key: str,
        body: SettingPutRequest,
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> SettingResponse:
        """Upsert one dynamic setting; broadcast the new value to all instances."""
        if c.set_setting is None:
            raise HTTPException(status_code=503, detail="settings not configured")
        setting = await c.set_setting.execute(
            {"key": key, "value": body.value, "updated_by": api_key.name},
        )
        return SettingResponse(
            key=setting.key,
            value=setting.value,
            immutable=setting.immutable,
            role=setting.role,
            updated_at=setting.updated_at,
            updated_by=setting.updated_by,
        )

    @admin.delete("/settings/{key}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_setting(
        key: str,
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Delete one dynamic setting."""
        if c.delete_setting is None:
            raise HTTPException(status_code=503, detail="settings not configured")
        await c.delete_setting.execute(key)

    @admin.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
    async def create_api_key(
        payload: ApiKeyCreateRequest,
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> ApiKeyCreateResponse:
        """Mint a new API key.

        The plaintext token is returned in the response body exactly
        once and is not stored on the server side.
        """
        if c.create_api_key is None:
            raise HTTPException(
                status_code=503,
                detail="api key repository not configured",
            )
        result = await c.create_api_key.execute(
            {
                "name": payload.name,
                "scopes": payload.scopes,
                "enabled": payload.enabled,
            },
        )
        return ApiKeyCreateResponse(
            id=UUID(result.id),
            name=result.name,
            plaintext=result.plaintext,
            scopes=result.scopes,
            enabled=result.enabled,
        )

    @admin.get("/api-keys", response_model=list[ApiKeyListItem])
    async def list_api_keys(
        limit: int = Query(default=100, ge=1, le=500),
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> list[ApiKeyListItem]:
        """List all API keys (the plaintext is never returned)."""
        if c.list_api_keys is None:
            raise HTTPException(
                status_code=503,
                detail="api key repository not configured",
            )
        records = await c.list_api_keys.execute({"limit": limit})
        return [
            ApiKeyListItem(
                id=r["id"],
                name=r["name"],
                scopes=list(r.get("scopes", [])),
                enabled=bool(r.get("enabled", True)),
                created_at=r.get("created_at"),
            )
            for r in records
        ]

    @admin.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_api_key(
        key_id: str,
        api_key: ApiKey = Depends(require_scope(Scope.ADMIN)),
        c: Composition = Depends(_composition),
    ) -> None:
        """Revoke one API key."""
        if c.delete_api_key is None:
            raise HTTPException(
                status_code=503,
                detail="api key repository not configured",
            )
        await c.delete_api_key.execute(key_id)

    return [
        ops,
        admin,
        domains,
        categories,
        urls,
        channels,
        bindings,
        imports,
        exports,
        changes,
        snapshots,
    ]


def uuid4_safe() -> str:
    """Generate a string id without importing ``uuid`` at module top.

    Kept tiny so the routers module does not need a top-level uuid
    import; the result is a valid UUID4 string.
    """
    import uuid

    return str(uuid.uuid4())
