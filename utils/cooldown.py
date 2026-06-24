from __future__ import annotations

from datetime import UTC, datetime, timedelta


class CooldownManager:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self._entries: dict[int, datetime] = {}

    def is_on_cooldown(self, key: int) -> bool:
        last_seen = self._entries.get(key)
        if last_seen is None:
            return False
        return datetime.now(UTC) - last_seen < timedelta(seconds=self.seconds)

    def remaining_seconds(self, key: int) -> int:
        last_seen = self._entries.get(key)
        if last_seen is None:
            return 0
        expiry = last_seen + timedelta(seconds=self.seconds)
        remaining = int((expiry - datetime.now(UTC)).total_seconds())
        return max(0, remaining)

    def touch(self, key: int) -> None:
        self._entries[key] = datetime.now(UTC)
