from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import Settings
from database import Database, MessageXpResult
from utils import build_daily_claim_embed, build_error_embed, calculate_level, calculate_required_xp

LOGGER = logging.getLogger(__name__)


def _format_remaining(seconds: int) -> str:
    hours, remainder = divmod(max(seconds, 0), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}h {minutes}m {secs}s"


class RewardsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.settings: Settings = bot.settings  # type: ignore[attr-defined]

    @app_commands.command(name="daily", description="Claim your daily XP reward.")
    async def daily(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            user_before = await self.db.get_or_create_user(interaction.user.id)
            max_xp = calculate_required_xp(self.settings.max_level)
            result = await self.db.claim_daily(interaction.user.id, self.settings.daily_reward, max_xp=max_xp)
            if result.claimed:
                new_total_xp = min(result.xp, max_xp)
                new_level = calculate_level(new_total_xp, max_level=self.settings.max_level)
                await self.db.update_level(interaction.user.id, new_level)
                if new_level > user_before.level and interaction.guild is not None:
                    leveling_cog = self.bot.get_cog("LevelingCog")
                    if leveling_cog is not None:
                        level_result = MessageXpResult(
                            xp_awarded=self.settings.daily_reward,
                            total_xp=result.xp,
                            new_level=new_level,
                            daily_xp_earned=user_before.daily_xp_earned,
                            daily_xp_remaining=max(0, self.settings.daily_xp_cap - user_before.daily_xp_earned),
                            level_up=True,
                            reached_daily_cap=False,
                            already_capped=False,
                            reached_max_level=new_level >= self.settings.max_level or result.xp >= max_xp,
                        )
                        await leveling_cog._handle_level_up(interaction.user, interaction.guild, level_result)
                if result.awarded_xp > 0:
                    detail = f"Your daily XP reward added {result.awarded_xp} XP to your profile."
                else:
                    detail = "You're already at the XP cap for max level, so your streak was updated without adding more XP."
            else:
                detail = f"You can claim again in {_format_remaining(result.remaining_seconds)}."

            embed = build_daily_claim_embed(
                result.claimed,
                result.awarded_xp if result.claimed else self.settings.daily_reward,
                result.streak,
                detail,
                self.settings.embed_color,
            )
            LOGGER.info("/daily used by %s.", interaction.user.id)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            LOGGER.exception("Failed to process daily reward for user %s.", interaction.user.id)
            await interaction.followup.send(
                embed=build_error_embed("The daily reward could not be processed.", self.settings.embed_color),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RewardsCog(bot))
