from __future__ import annotations

from typing import Any

from lens_application.ports import DeadLetterRepositoryPort

__all__ = [
    "InMemoryDeadLetterStore",
    "RedisDeadLetterStore",
]


class InMemoryDeadLetterStore(DeadLetterRepositoryPort):
    def __init__(self) -> None:
        self._queues: dict[str, list[dict[str, Any]]] = {}

    async def add(self, *, queue: str, message_id: str, body: dict[str, Any], error: str | None = None) -> None:
        if queue not in self._queues:
            self._queues[queue] = []
        self._queues[queue].append(
            {
                "message_id": message_id,
                "body": body,
                "attempts": 1,
                "last_error": error,
                "queue": queue,
            },
        )

    async def list_messages(self, *, queue: str, limit: int = 100) -> list[dict[str, Any]]:
        if queue not in self._queues:
            return []
        return self._queues[queue][:limit]

    async def replay(self, message_ids: list[str]) -> int:
        return len(message_ids)

    async def discard(self, message_ids: list[str]) -> int:
        count = 0
        ids_set = set(message_ids)
        for queue_name in list(self._queues.keys()):
            kept = [m for m in self._queues[queue_name] if m["message_id"] not in ids_set]
            count += len(self._queues[queue_name]) - len(kept)
            self._queues[queue_name] = kept
        return count


class RedisDeadLetterStore(DeadLetterRepositoryPort):
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def add(
        self,
        *,
        queue: str,
        message_id: str,
        body: dict[str, Any],
        error: str | None = None,
    ) -> None:
        import json

        try:
            payload = json.dumps(
                {
                    "message_id": message_id,
                    "queue": queue,
                    "body": body,
                    "error": error,
                    "_raw": json.dumps(body),
                },
            )
            await self._redis.lpush(f"lens:dlq:{queue}", payload)
        except Exception:
            pass

    async def list_messages(self, *, queue: str, limit: int = 100) -> list[dict[str, Any]]:
        import json

        try:
            raw = await self._redis.lrange(f"lens:dlq:{queue}", 0, limit - 1)
        except Exception:
            return []
        messages: list[dict[str, Any]] = []
        for item in raw:
            try:
                messages.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue
        return messages

    async def replay(self, message_ids: list[str]) -> int:
        count = 0
        for queue_name in await self._dlq_queues():
            key = f"lens:dlq:{queue_name}"
            messages = await self.list_messages(queue=queue_name)
            for msg in messages:
                if msg.get("message_id") in message_ids:
                    await self._redis.lrem(key, 1, msg.get("_raw", ""))
                    count += 1
        return count

    async def discard(self, message_ids: list[str]) -> int:
        ids_set = set(message_ids)
        count = 0
        for queue_name in await self._dlq_queues():
            key = f"lens:dlq:{queue_name}"
            messages = await self.list_messages(queue=queue_name)
            for msg in messages:
                if msg.get("message_id") in ids_set:
                    await self._redis.lrem(key, 1, msg.get("_raw", ""))
                    count += 1
        return count

    async def _dlq_queues(self) -> list[str]:
        try:
            raw = await self._redis.keys("lens:dlq:*")
        except Exception:
            return []
        return [k.decode("utf-8").replace("lens:dlq:", "") for k in raw]
