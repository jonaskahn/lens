from __future__ import annotations

from typing import Any

from lens_application.ports import SettingsRepositoryPort

__all__ = [
    "InMemorySettingsStore",
]


class InMemorySettingsStore(SettingsRepositoryPort):
    def __init__(self) -> None:
        self._settings: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._settings.get(key)

    async def list_all(self) -> list[dict[str, Any]]:
        return [
            {
                "key": k,
                "value": v.get("value"),
                "immutable": v.get("immutable", False),
                "role": v.get("role"),
                "updated_at": v.get("updated_at"),
                "updated_by": v.get("updated_by"),
            }
            for k, v in self._settings.items()
        ]

    async def upsert(self, key: str, value: Any, *, updated_by: str) -> None:
        from datetime import UTC, datetime

        existing = self._settings.get(key)
        self._settings[key] = {
            "key": key,
            "value": value,
            "immutable": existing.get("immutable", False) if existing else False,
            "role": existing.get("role") if existing else None,
            "updated_at": datetime.now(UTC),
            "updated_by": updated_by,
        }

    async def delete(self, key: str) -> None:
        self._settings.pop(key, None)

    async def list_audit(self, key: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if key in self._settings:
            return [self._settings[key]]
        return []

    async def get_all_current(self) -> dict[str, Any]:
        return {k: v.get("value") for k, v in self._settings.items()}
