"""API tests for the check-now, history, diff, and snapshot endpoints."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from _api_fakes import InMemoryUnitOfWork, reset_in_memory_store
from fastapi.testclient import TestClient

from lens_api.main import create_app
from lens_api.settings import ApiSettings
from lens_application.use_cases import TriggerCheckUseCase
from lens_infrastructure.broker import InMemoryBroker, InMemoryTaskPublisher


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    reset_in_memory_store()


def _lookup_factory() -> Any:
    def _lookup(_key_hash: str) -> dict[str, Any] | None:
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "test",
            "scopes": ["read", "write", "admin"],
            "enabled": True,
        }

    return _lookup


def _client_with_publisher() -> tuple[TestClient, InMemoryBroker]:
    broker = InMemoryBroker()
    publisher = InMemoryTaskPublisher(broker)
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    composition = app.state.composition
    new_trigger = TriggerCheckUseCase(
        composition.uow_factory,
        publisher,
    )
    fields = {f: getattr(composition, f) for f in composition.__dataclass_fields__}
    fields["trigger_check"] = new_trigger
    fields["task_publisher"] = publisher
    app.state.composition = composition.__class__(**fields)
    return TestClient(app), broker


def _client() -> TestClient:
    publisher = InMemoryTaskPublisher(InMemoryBroker())
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    composition = app.state.composition
    new_trigger = TriggerCheckUseCase(
        composition.uow_factory,
        publisher,
    )
    fields = {f: getattr(composition, f) for f in composition.__dataclass_fields__}
    fields["trigger_check"] = new_trigger
    fields["task_publisher"] = publisher
    app.state.composition = composition.__class__(**fields)
    return TestClient(app)


def _client_no_publisher() -> TestClient:
    app = create_app(
        settings=ApiSettings(),
        uow_factory=InMemoryUnitOfWork,
        api_key_lookup=_lookup_factory(),
    )
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-key"}


def _seed_url(client: TestClient, host_suffix: str | None = None) -> str:
    """Create a unique domain and url for the test."""
    suffix = host_suffix or uuid4().hex[:8]
    host = f"shop-{suffix}.example.com"
    domain = client.post(
        "/api/v1/domains",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps({"host": host}),
    )
    assert domain.status_code == 201, domain.text
    url = client.post(
        "/api/v1/urls",
        headers={**_auth(), "Content-Type": "application/json"},
        content=json.dumps(
            {
                "domain_id": domain.json()["id"],
                "address": f"https://{host}/p/1",
                "interval_seconds": 600,
            },
        ),
    )
    assert url.status_code == 201, url.text
    return url.json()["id"]


def test_given_url_when_check_now_then_enqueued() -> None:
    client, broker = _client_with_publisher()
    url_id = _seed_url(client, host_suffix="one")
    response = client.post(f"/api/v1/urls/{url_id}/check", headers=_auth())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enqueued"] == 1
    assert url_id in body["url_ids"]
    queue = broker.attach_consumer("crawl.task")
    assert queue.qsize() == 1


def test_given_domain_when_check_now_then_enqueues_urls() -> None:
    client, broker = _client_with_publisher()
    url_id = _seed_url(client, host_suffix="two")
    domain_id = client.get(
        f"/api/v1/urls/{url_id}",
        headers=_auth(),
    ).json()["domain_id"]
    response = client.post(
        f"/api/v1/domains/{domain_id}/check",
        headers=_auth(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enqueued"] == 1
    queue = broker.attach_consumer("crawl.task")
    assert queue.qsize() == 1


def test_given_no_changes_when_list_url_changes_then_empty() -> None:
    client = _client()
    url_id = _seed_url(client, host_suffix="three")
    response = client.get(f"/api/v1/urls/{url_id}/changes", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []


def test_given_no_publisher_when_check_now_then_503() -> None:
    client = _client_no_publisher()
    url_id = _seed_url(client, host_suffix="four")
    response = client.post(f"/api/v1/urls/{url_id}/check", headers=_auth())
    assert response.status_code == 503
