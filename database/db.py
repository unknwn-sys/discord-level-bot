from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg

from utils.xp import calculate_level

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class UserRecord:
    user_id: int
    xp: int
    level: int
    messages: int
    voice_minutes: int
    daily_streak: int
    reputation: int
    daily_xp_earned: int
    daily_xp_date: date | None
    last_daily: datetime | None
    last_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class DailyClaimResult:
    claimed: bool
    xp: int
    awarded_xp: int
    streak: int
    next_claim_at: datetime | None
    remaining_seconds: int


@dataclass(slots=True)
class MessageXpResult:
    xp_awarded: int
    total_xp: int
    new_level: int
    daily_xp_earned: int
    daily_xp_remaining: int
    level_up: bool
    reached_daily_cap: bool
    already_capped: bool
    reached_max_level: bool


class Database:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10, command_timeout=30)
        LOGGER.info("Connected to PostgreSQL.")

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
            LOGGER.info("Closed PostgreSQL connection pool.")

    async def initialize(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8")
        await self.execute(schema_sql)
        await self._run_migrations()
        LOGGER.info("Database schema ensured and migrations applied.")

    async def create_user(self, user_id: int) -> UserRecord:
        await self.execute(
            """
            INSERT INTO users (user_id, daily_xp_date)
            VALUES ($1, CURRENT_DATE)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )
        user = await self.get_user(user_id)
        if user is None:
            raise RuntimeError(f"Failed to create user record for {user_id}.")
        return user

    async def get_user(self, user_id: int) -> UserRecord | None:
        row = await self.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return self._to_user_record(row) if row else None

    async def get_or_create_user(self, user_id: int) -> UserRecord:
        user = await self.get_user(user_id)
        if user is None:
            user = await self.create_user(user_id)
        return await self.reset_daily_xp_if_needed(user)

    async def reset_daily_xp_if_needed(self, user: UserRecord) -> UserRecord:
        today = datetime.now(UTC).date()
        if user.daily_xp_date == today:
            return user

        await self.execute(
            """
            UPDATE users
            SET daily_xp_earned = 0,
                daily_xp_date = $2
            WHERE user_id = $1
            """,
            user.user_id,
            today,
        )
        refreshed = await self.get_user(user.user_id)
        if refreshed is None:
            raise RuntimeError(f"Failed to refresh user record for {user.user_id}.")
        return refreshed

    async def update_level(self, user_id: int, level: int) -> None:
        await self.execute(
            """
            UPDATE users
            SET level = $2
            WHERE user_id = $1
            """,
            user_id,
            level,
        )

    async def set_last_message(self, user_id: int, content: str) -> None:
        await self.execute(
            """
            UPDATE users
            SET last_message = $2
            WHERE user_id = $1
            """,
            user_id,
            content,
        )

    async def apply_message_xp(
        self,
        user_id: int,
        raw_xp_gain: int,
        content: str,
        daily_cap: int,
        max_xp: int,
        max_level: int,
    ) -> MessageXpResult:
        user = await self.get_or_create_user(user_id)
        if user.level >= max_level or user.xp >= max_xp:
            await self.execute(
                """
                UPDATE users
                SET messages = messages + 1,
                    last_message = $2
                WHERE user_id = $1
                """,
                user_id,
                content,
            )
            return MessageXpResult(
                xp_awarded=0,
                total_xp=user.xp,
                new_level=user.level,
                daily_xp_earned=user.daily_xp_earned,
                daily_xp_remaining=max(0, daily_cap - user.daily_xp_earned),
                level_up=False,
                reached_daily_cap=user.daily_xp_earned >= daily_cap,
                already_capped=user.daily_xp_earned >= daily_cap,
                reached_max_level=True,
            )

        remaining_today = max(0, daily_cap - user.daily_xp_earned)
        if remaining_today <= 0:
            await self.execute(
                """
                UPDATE users
                SET messages = messages + 1,
                    last_message = $2
                WHERE user_id = $1
                """,
                user_id,
                content,
            )
            return MessageXpResult(
                xp_awarded=0,
                total_xp=user.xp,
                new_level=user.level,
                daily_xp_earned=user.daily_xp_earned,
                daily_xp_remaining=0,
                level_up=False,
                reached_daily_cap=True,
                already_capped=True,
                reached_max_level=False,
            )

        awardable_xp = min(raw_xp_gain, remaining_today, max(0, max_xp - user.xp))
        total_xp = user.xp + awardable_xp
        next_level = calculate_level(total_xp, max_level=max_level)
        reached_max_level = total_xp >= max_xp or next_level >= max_level
        daily_xp_earned = user.daily_xp_earned + awardable_xp
        daily_xp_remaining = max(0, daily_cap - daily_xp_earned)

        await self.execute(
            """
            UPDATE users
            SET xp = xp + $2,
                level = $3,
                messages = messages + 1,
                last_message = $4,
                daily_xp_earned = $5,
                daily_xp_date = $6
            WHERE user_id = $1
            """,
            user_id,
            awardable_xp,
            next_level,
            content,
            daily_xp_earned,
            datetime.now(UTC).date(),
        )

        return MessageXpResult(
            xp_awarded=awardable_xp,
            total_xp=total_xp,
            new_level=next_level,
            daily_xp_earned=daily_xp_earned,
            daily_xp_remaining=daily_xp_remaining,
            level_up=next_level > user.level,
            reached_daily_cap=daily_xp_earned >= daily_cap,
            already_capped=False,
            reached_max_level=reached_max_level,
        )

    async def get_rank(self, user_id: int) -> int | None:
        row = await self.fetchrow(
            """
            SELECT rank_position
            FROM (
                SELECT user_id, ROW_NUMBER() OVER (ORDER BY xp DESC, updated_at ASC) AS rank_position
                FROM users
            ) ranked
            WHERE user_id = $1
            """,
            user_id,
        )
        return int(row["rank_position"]) if row else None

    async def get_top_users(self, limit: int = 10) -> list[UserRecord]:
        rows = await self.fetch(
            """
            SELECT *
            FROM users
            ORDER BY xp DESC, updated_at ASC
            LIMIT $1
            """,
            limit,
        )
        users = [self._to_user_record(row) for row in rows]
        return [await self.reset_daily_xp_if_needed(user) for user in users]

    async def get_leaderboard_message_id(self, channel_id: int) -> int | None:
        row = await self.fetchrow(
            """
            SELECT message_id
            FROM leaderboard_state
            WHERE channel_id = $1
            """,
            channel_id,
        )
        if row is None or row["message_id"] is None:
            return None
        return int(row["message_id"])

    async def set_leaderboard_message_id(self, channel_id: int, message_id: int | None) -> None:
        await self.execute(
            """
            INSERT INTO leaderboard_state (channel_id, message_id, updated_at)
            VALUES ($1, $2, TIMEZONE('utc', NOW()))
            ON CONFLICT (channel_id) DO UPDATE
            SET message_id = EXCLUDED.message_id,
                updated_at = EXCLUDED.updated_at
            """,
            channel_id,
            message_id,
        )

    async def claim_daily(self, user_id: int, reward_xp: int, max_xp: int) -> DailyClaimResult:
        user = await self.get_or_create_user(user_id)
        now = datetime.now(UTC)
        next_claim_at: datetime | None = None

        if user.last_daily is not None:
            next_claim_at = user.last_daily + timedelta(hours=24)
            if next_claim_at > now:
                remaining = int((next_claim_at - now).total_seconds())
                return DailyClaimResult(
                    claimed=False,
                    xp=user.xp,
                    awarded_xp=0,
                    streak=user.daily_streak,
                    next_claim_at=next_claim_at,
                    remaining_seconds=remaining,
                )

        streak = 1
        if user.last_daily is not None and now - user.last_daily <= timedelta(hours=48):
            streak = user.daily_streak + 1

        awarded_xp = min(reward_xp, max(0, max_xp - user.xp))

        await self.execute(
            """
            UPDATE users
            SET xp = xp + $2,
                daily_streak = $3,
                last_daily = $4
            WHERE user_id = $1
            """,
            user_id,
            awarded_xp,
            streak,
            now,
        )

        return DailyClaimResult(
            claimed=True,
            xp=user.xp + awarded_xp,
            awarded_xp=awarded_xp,
            streak=streak,
            next_claim_at=now + timedelta(hours=24),
            remaining_seconds=0,
        )

    async def update_voice_time(self, user_id: int, minutes: int, xp_delta: int = 0, new_level: int | None = None) -> None:
        if new_level is None:
            await self.execute(
                """
                UPDATE users
                SET voice_minutes = voice_minutes + $2,
                    xp = xp + $3
                WHERE user_id = $1
                """,
                user_id,
                minutes,
                xp_delta,
            )
            return

        await self.execute(
            """
            UPDATE users
            SET voice_minutes = voice_minutes + $2,
                xp = xp + $3,
                level = $4
            WHERE user_id = $1
            """,
            user_id,
            minutes,
            xp_delta,
            new_level,
        )

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            return await connection.execute(query, *args)

    def _require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Database pool has not been initialized.")
        return self.pool

    async def _run_migrations(self) -> None:
        migration_statements = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_xp_earned INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_xp_date DATE",
            "UPDATE users SET daily_xp_date = CURRENT_DATE WHERE daily_xp_date IS NULL",
            """
            CREATE TABLE IF NOT EXISTS leaderboard_state (
                channel_id BIGINT PRIMARY KEY,
                message_id BIGINT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
            )
            """,
        ]
        for statement in migration_statements:
            await self.execute(statement)

    @staticmethod
    def _to_user_record(row: asyncpg.Record) -> UserRecord:
        return UserRecord(
            user_id=int(row["user_id"]),
            xp=int(row["xp"]),
            level=int(row["level"]),
            messages=int(row["messages"]),
            voice_minutes=int(row["voice_minutes"]),
            daily_streak=int(row["daily_streak"]),
            reputation=int(row["reputation"]),
            daily_xp_earned=int(row["daily_xp_earned"]),
            daily_xp_date=row["daily_xp_date"],
            last_daily=row["last_daily"],
            last_message=row["last_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
