from __future__ import annotations

from datetime import UTC, datetime

import discord


def _base_embed(title: str, description: str, color: int) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(UTC))


def build_error_embed(message: str, color: int) -> discord.Embed:
    return _base_embed("Something went wrong", message, color)


def build_daily_cap_embed(daily_cap: int, color: int) -> discord.Embed:
    embed = _base_embed(
        "Daily Message XP Limit Reached",
        f"You've reached today's message XP limit ({daily_cap} XP).\nCome back tomorrow to continue earning XP.",
        color,
    )
    return embed


def build_level_up_embed(
    member: discord.abc.User,
    level: int,
    xp: int,
    rank: int | None,
    progress_percent: int,
    max_level: int,
    color: int,
) -> discord.Embed:
    title = "LEVEL UP!"
    description = f"{member.mention} reached Level {level}."
    embed = _base_embed(title, description, color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Reached Level", value="MAX LEVEL" if level >= max_level else str(level), inline=True)
    embed.add_field(name="Rank", value=f"#{rank}" if rank else "Unranked", inline=True)
    embed.add_field(name="Current XP", value=str(xp), inline=True)
    embed.add_field(
        name="Progress To Next Level",
        value="MAX LEVEL" if level >= max_level else f"{progress_percent}%",
        inline=True,
    )
    embed.set_footer(text="Keep chatting to earn more XP!" if level < max_level else "You reached the level cap.")
    return embed


def build_rank_embed(
    member: discord.abc.User,
    level_label: str,
    xp: int,
    rank: int | None,
    xp_needed: str,
    daily_progress: str,
    daily_remaining: str,
    color: int,
) -> discord.Embed:
    embed = _base_embed(f"{member.display_name}'s Rank", "Level and daily XP progress.", color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Current Level", value=level_label, inline=True)
    embed.add_field(name="Total XP", value=str(xp), inline=True)
    embed.add_field(name="Rank Position", value=f"#{rank}" if rank else "Unranked", inline=True)
    embed.add_field(name="XP Needed For Next Level", value=xp_needed, inline=True)
    embed.add_field(name="Daily XP Earned", value=daily_progress, inline=True)
    embed.add_field(name="Daily XP Remaining", value=daily_remaining, inline=True)
    return embed


def build_profile_embed(
    member: discord.abc.User,
    level_label: str,
    xp: int,
    rank: int | None,
    messages: int,
    voice_minutes: int,
    daily_streak: int,
    daily_progress: str,
    color: int,
) -> discord.Embed:
    embed = _base_embed(f"{member.display_name}'s Profile", "Community activity summary.", color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=level_label, inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="Rank", value=f"#{rank}" if rank else "Unranked", inline=True)
    embed.add_field(name="Messages", value=str(messages), inline=True)
    embed.add_field(name="Voice Minutes", value=str(voice_minutes), inline=True)
    embed.add_field(name="Daily Streak", value=str(daily_streak), inline=True)
    embed.add_field(name="Daily XP Progress", value=daily_progress, inline=False)
    return embed


def build_leaderboard_embed(entries: list[tuple[str, int, int]], color: int) -> discord.Embed:
    embed = _base_embed("🏆 Community Leaderboard", "Top 10 users by total XP.", color)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    if not entries:
        embed.description = "No leaderboard data is available yet."
        return embed

    for index, (name, level, xp) in enumerate(entries, start=1):
        prefix = medals.get(index, f"#{index}")
        embed.add_field(
            name=f"{prefix} {name}",
            value=f"Level {level}\n{xp} XP",
            inline=False,
        )
    return embed


def build_daily_claim_embed(claimed: bool, xp_amount: int, streak: int, detail: str, color: int) -> discord.Embed:
    title = "Daily Reward Claimed" if claimed else "Daily Reward Unavailable"
    embed = _base_embed(title, detail, color)
    embed.add_field(name="Reward XP", value=str(xp_amount), inline=True)
    embed.add_field(name="Daily Streak", value=str(streak), inline=True)
    return embed
