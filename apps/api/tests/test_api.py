"""Integration-style tests for the FastAPI app.

These tests use the in-memory UoW + a permissive API-key stub so the full
HTTP surface (routing, request/response schemas, auth) can be exercised
without a Postgres database.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from _api_fakes import InMemoryUnitOfWork, reset_in_memory_store
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from lens_api.main import create_app
from lens_api.rate_limit import resolve_rate_limit_key
from lens_api.settings import ApiSettings


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    reset_in_memory_store()


def _lookup_factory() -> Any:
    """Return an api_key_lookup that grants read/write/admin to any key."""

    def _lookup(_key_hash: str) -> dict[str, Any] | None:
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "test",
            "scopes": ["read", "write", "admin"],
            "enabled": True,
        }

    return _lookup


def _client() -> TestClient:
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-key"}


def test_given_setup_imported_when_list_urls_then_round_trip() -> None:
    client = _client()
    payload = {
        "version": 1,
        "domains": [
            {
                "host": "shop.example.com",
                "categories": [
                    {
                        "name": "products",
                        "urls": [
                            {
                                "address": "https://shop.example.com/p/1",
                                "interval_seconds": 600,
                            },
                            {
                                "address": "https://shop.example.com/p/2",
                                "interval_seconds": 600,
                            },
                        ],
                    },
                ],
            },
        ],
    }
    response = client.post(
        "/api/v1/imports?on_conflict=skip",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps(payload),
    )
    assert response.status_code == 200, response.text

    listing = client.get("/api/v1/urls", headers=_auth())
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is None
    addresses = {u["address"] for u in body["items"]}
    assert "https://shop.example.com/p/1" in addresses
    assert "https://shop.example.com/p/2" in addresses


def test_given_no_auth_when_list_domains_then_401() -> None:
    client = _client()
    response = client.get("/api/v1/domains")
    assert response.status_code == 401


def test_given_create_domain_then_get_returns_same() -> None:
    client = _client()
    create = client.post(
        "/api/v1/domains",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"host": "example.com", "display_name": "Example"}),
    )
    assert create.status_code == 201
    body = create.json()
    get = client.get(f"/api/v1/domains/{body['id']}", headers=_auth())
    assert get.status_code == 200
    assert get.json()["host"] == "example.com"


def test_given_invalid_body_when_create_domain_then_422() -> None:
    client = _client()
    response = client.post(
        "/api/v1/domains",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({}),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "errors" in body["error"]["details"]


def test_given_invalid_on_conflict_when_import_then_422() -> None:
    client = _client()
    response = client.post(
        "/api/v1/imports?on_conflict=bogus",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"version": 1, "domains": []}),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "skip" in body["error"]["details"]["allowed"]


def test_given_invalid_since_when_list_changes_then_422() -> None:
    client = _client()
    create = client.post(
        "/api/v1/domains",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"host": "since.example.com"}),
    )
    domain_id = create.json()["id"]
    url = client.post(
        "/api/v1/urls",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps(
            {
                "domain_id": domain_id,
                "address": "https://since.example.com/p/1",
                "interval_seconds": 600,
            },
        ),
    )
    url_id = url.json()["id"]
    response = client.get(
        f"/api/v1/urls/{url_id}/changes?since=not-a-date",
        headers=_auth(),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


def test_given_duplicate_host_when_create_domain_then_409() -> None:
    client = _client()
    first = client.post(
        "/api/v1/domains",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"host": "example.com"}),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/domains",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"host": "example.com"}),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_given_missing_when_get_domain_then_404() -> None:
    client = _client()
    response = client.get(
        "/api/v1/domains/00000000-0000-0000-0000-000000000000",
        headers=_auth(),
    )
    assert response.status_code == 404


def test_given_import_yaml_when_called_then_parses() -> None:
    client = _client()
    yaml_body = (
        "version: 1\n"
        "domains:\n"
        "  - host: news.example.com\n"
        "    categories:\n"
        "      - name: articles\n"
        "        urls:\n"
        "          - address: https://news.example.com/a/1\n"
        "            interval_seconds: 600\n"
    )
    response = client.post(
        "/api/v1/imports",
        headers={**_auth(), "Content-Type": "application/x-yaml"},
        content=yaml_body,
    )
    assert response.status_code == 200


def test_given_request_when_resolved_then_response_carries_correlation_id() -> None:
    client = _client()
    response = client.get(
        "/api/v1/domains",
        headers={**_auth(), "X-Correlation-Id": "abc-123"},
    )
    assert response.headers.get("X-Correlation-Id") == "abc-123"


def test_given_request_without_correlation_id_when_resolved_then_generated() -> None:
    client = _client()
    response = client.get("/api/v1/domains", headers=_auth())
    cid = response.headers.get("X-Correlation-Id")
    assert cid is not None
    assert len(cid) > 0


def test_given_streaming_response_when_correlation_middleware_then_header_passes_through() -> None:
    """The ASGI correlation middleware must not buffer streaming responses."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    from lens_api.correlation import CorrelationIdMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/stream")
    async def _stream() -> StreamingResponse:
        async def _generator():
            yield b"chunk-1\n"
            yield b"chunk-2\n"

        return StreamingResponse(_generator(), media_type="text/plain")

    client = TestClient(app)
    response = client.get("/stream", headers={"X-Correlation-Id": "stream-cid"})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-Id") == "stream-cid"
    assert response.text == "chunk-1\nchunk-2\n"


def test_given_request_with_api_key_when_resolve_rate_key_then_per_key_bucket() -> None:
    scope: dict[str, str] = {"type": "http", "method": "GET", "headers": []}
    request = Request(scope=scope)
    request.state.api_key_id = "00000000-0000-0000-0000-000000000001"
    assert resolve_rate_limit_key(request) == "rate:key:00000000-0000-0000-0000-000000000001"


def test_given_request_without_api_key_when_resolve_rate_key_then_peer_fallback() -> None:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "headers": [(b"x-forwarded-for", b"1.2.3.4")],
        "client": ("9.9.9.9", 1234),
    }
    request = Request(scope=scope)
    key = resolve_rate_limit_key(request)
    assert key == "rate:ip:9.9.9.9"
    assert "1.2.3.4" not in key


def test_given_app_factory_when_called_with_rate_limiter_then_used() -> None:
    from lens_api.rate_limit import RateLimiter

    class _StaticLimiter(RateLimiter):
        async def is_allowed(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
            return True

        async def reset(self, key: str) -> None:
            return None

    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
        rate_limiter=_StaticLimiter(),
    )
    assert isinstance(app, FastAPI)
    assert app.title == "lens API"


def test_given_production_composition_when_built_then_includes_async_storage() -> None:
    """Production composition wires AsyncLocalFileBlobStorage + db lookup."""
    from sqlalchemy import create_engine

    from lens_api.production import build_production_composition
    from lens_infrastructure.storage import AsyncLocalFileBlobStorage

    engine = create_engine("sqlite:///:memory:")
    composition, lookup = build_production_composition(
        engine,
        blob_root="/tmp/lens-blob-test",
    )
    assert composition is not None
    assert composition.get_change_diff_blob is not None
    assert composition.enforce_retention is not None
    assert composition.sweep_orphans is not None
    assert isinstance(composition.get_change_diff_blob._blob, AsyncLocalFileBlobStorage)
    assert lookup is not None


def test_given_no_api_key_repo_when_create_api_key_then_503() -> None:
    client = _client()
    response = client.post(
        "/api/v1/admin/api-keys",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"name": "ci-key", "scopes": ["read", "write"]}),
    )
    assert response.status_code == 503


def test_given_api_key_repo_when_create_api_key_then_returns_plaintext_once() -> None:
    from _fakes import InMemoryApiKeyRepository

    from lens_api.composition import build_composition

    repo = InMemoryApiKeyRepository()
    composition = build_composition(InMemoryUnitOfWork, api_key_repo=repo)
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    app.state.composition = composition
    client = TestClient(app)
    response = client.post(
        "/api/v1/admin/api-keys",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"name": "ci-key", "scopes": ["read", "write"]}),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "ci-key"
    assert "plaintext" in body
    assert len(body["plaintext"]) >= 32
    assert "read" in body["scopes"]


def test_given_api_key_repo_when_list_api_keys_then_returns_records() -> None:
    from _fakes import InMemoryApiKeyRepository

    from lens_api.composition import build_composition

    repo = InMemoryApiKeyRepository()
    composition = build_composition(InMemoryUnitOfWork, api_key_repo=repo)
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    app.state.composition = composition
    client = TestClient(app)
    create = client.post(
        "/api/v1/admin/api-keys",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"name": "ci-key", "scopes": ["read"]}),
    )
    assert create.status_code == 201
    list_resp = client.get("/api/v1/admin/api-keys", headers=_auth())
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert len(body) == 1
    assert "plaintext" not in body[0]


def test_given_api_key_repo_when_delete_api_key_then_revokes() -> None:
    from _fakes import InMemoryApiKeyRepository

    from lens_api.composition import build_composition

    repo = InMemoryApiKeyRepository()
    composition = build_composition(InMemoryUnitOfWork, api_key_repo=repo)
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    app.state.composition = composition
    client = TestClient(app)
    create = client.post(
        "/api/v1/admin/api-keys",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"name": "ci-key", "scopes": ["read"]}),
    )
    key_id = create.json()["id"]
    response = client.delete(f"/api/v1/admin/api-keys/{key_id}", headers=_auth())
    assert response.status_code == 204
    list_resp = client.get("/api/v1/admin/api-keys", headers=_auth())
    assert list_resp.json() == []
