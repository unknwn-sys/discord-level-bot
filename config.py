from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

MAX_LEVEL = 50
DAILY_XP_CAP = 20


def _parse_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value, 0)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


@dataclass(slots=True)
class Settings:
    discord_token: str
    database_url: str
    command_prefix: str = "!"
    xp_cooldown: int = 60
    daily_reward: int = 100
    daily_xp_cap: int = DAILY_XP_CAP
    max_level: int = MAX_LEVEL
    voice_xp_reward: int = 10
    voice_xp_interval_minutes: int = 5
    embed_color: int = 0x5865F2
    bot_commands_channel_id: int | None = None
    leaderboard_channel_id: int | None = None
    role_rewards: dict[int, str] = field(
        default_factory=lambda: {
            5: "Member",
            10: "Veteran",
            20: "Elite",
            30: "Legend",
        }
    )


def get_settings() -> Settings:
    discord_token = os.getenv("DISCORD_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not discord_token:
        raise ValueError("DISCORD_TOKEN is required.")
    if not database_url:
        raise ValueError("DATABASE_URL is required.")

    bot_commands_channel_raw = os.getenv("BOT_COMMANDS_CHANNEL_ID", "").strip()
    bot_commands_channel_id = int(bot_commands_channel_raw) if bot_commands_channel_raw else None
    leaderboard_channel_raw = os.getenv("LEADERBOARD_CHANNEL_ID", "").strip()
    leaderboard_channel_id = int(leaderboard_channel_raw) if leaderboard_channel_raw else None

    return Settings(
        discord_token=discord_token,
        database_url=database_url,
        command_prefix=os.getenv("COMMAND_PREFIX", "!"),
        xp_cooldown=_parse_int("XP_COOLDOWN", 60),
        daily_reward=_parse_int("DAILY_REWARD", 100),
        daily_xp_cap=_parse_int("DAILY_XP_CAP", DAILY_XP_CAP),
        max_level=_parse_int("MAX_LEVEL", MAX_LEVEL),
        voice_xp_reward=_parse_int("VOICE_XP_REWARD", 10),
        voice_xp_interval_minutes=_parse_int("VOICE_XP_INTERVAL_MINUTES", 5),
        embed_color=_parse_int("EMBED_COLOR", 0x5865F2),
        bot_commands_channel_id=bot_commands_channel_id,
        leaderboard_channel_id=leaderboard_channel_id,
    )
