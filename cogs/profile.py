from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import Settings
from database import Database
from utils import (
    build_error_embed,
    build_profile_embed,
    build_rank_embed,
    calculate_progress,
    generate_rank_card,
)

LOGGER = logging.getLogger(__name__)


def _format_level_label(level: int, max_level: int) -> str:
    return "MAX LEVEL" if level >= max_level else str(level)


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.settings: Settings = bot.settings  # type: ignore[attr-defined]

    @app_commands.command(name="rank", description="Show a user's level, XP, and rank.")
    @app_commands.describe(user="Optional member to inspect.")
    async def rank(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        await interaction.response.defer()
        target = user or interaction.user
        try:
            record = await self.db.get_or_create_user(target.id)
            rank = await self.db.get_rank(target.id)
            current_progress, needed_for_next, _, at_max = calculate_progress(record.xp, max_level=self.settings.max_level)
            xp_needed = "MAX LEVEL" if at_max or record.level >= self.settings.max_level else str(needed_for_next - current_progress)
            embed = build_rank_embed(
                target,
                _format_level_label(record.level, self.settings.max_level),
                record.xp,
                rank,
                xp_needed,
                f"{record.daily_xp_earned} / {self.settings.daily_xp_cap}",
                f"{max(0, self.settings.daily_xp_cap - record.daily_xp_earned)} XP",
                self.settings.embed_color,
            )
            LOGGER.info("/rank used by %s for target %s.", interaction.user.id, target.id)
            await interaction.followup.send(embed=embed)
        except Exception:
            LOGGER.exception("Failed to render rank for user %s.", target.id)
            await interaction.followup.send(
                embed=build_error_embed("The rank data could not be loaded.", self.settings.embed_color),
                ephemeral=True,
            )

    @app_commands.command(name="profile", description="Show a full activity profile.")
    async def profile(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            record = await self.db.get_or_create_user(interaction.user.id)
            rank = await self.db.get_rank(interaction.user.id)
            embed = build_profile_embed(
                interaction.user,
                _format_level_label(record.level, self.settings.max_level),
                record.xp,
                rank,
                record.messages,
                record.voice_minutes,
                record.daily_streak,
                f"{record.daily_xp_earned} / {self.settings.daily_xp_cap}",
                self.settings.embed_color,
            )
            LOGGER.info("/profile used by %s.", interaction.user.id)
            await interaction.followup.send(embed=embed)
        except Exception:
            LOGGER.exception("Failed to render profile for user %s.", interaction.user.id)
            await interaction.followup.send(
                embed=build_error_embed("The profile could not be loaded.", self.settings.embed_color),
                ephemeral=True,
            )

    @app_commands.command(name="rankcard", description="Generate a rank card image.")
    @app_commands.describe(user="Optional member to inspect.")
    async def rankcard(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        try:
            await interaction.response.defer(thinking=True)
        except discord.NotFound:
            LOGGER.warning("Rankcard interaction expired before it could be acknowledged for user %s.", interaction.user.id)
            return
        target = user or interaction.user
        try:
            record = await self.db.get_or_create_user(target.id)
            rank = await self.db.get_rank(target.id)
            rank_card = await generate_rank_card(
                target,
                record.level,
                record.xp,
                rank,
                record.daily_xp_earned,
                self.settings.daily_xp_cap,
                self.settings.max_level,
            )
            LOGGER.info("/rankcard used by %s for target %s.", interaction.user.id, target.id)
            await interaction.followup.send(file=rank_card)
        except Exception:
            LOGGER.exception("Failed to generate rank card for user %s.", target.id)
            await interaction.followup.send(
                embed=build_error_embed("The rank card could not be generated.", self.settings.embed_color),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
