from __future__ import annotations

import logging
import datetime


import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Settings
from database import Database
from utils import build_error_embed, build_leaderboard_embed

LOGGER = logging.getLogger(__name__)


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.settings: Settings = bot.settings  # type: ignore[attr-defined]
        if self.settings.leaderboard_channel_id:
            LOGGER.info("Starting daily leaderboard task.")
            self.hourly_leaderboard.start()

    def cog_unload(self) -> None:
        if self.hourly_leaderboard.is_running():
            self.hourly_leaderboard.cancel()

    @app_commands.command(name="leaderboard", description="Show the top 10 users by XP.")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            embed = await self._build_leaderboard_embed()
            LOGGER.info("/leaderboard used by %s.", interaction.user.id)
            await interaction.followup.send(embed=embed)
        except Exception:
            LOGGER.exception("Failed to render leaderboard.")
            await interaction.followup.send(
                embed=build_error_embed("The leaderboard could not be loaded right now.", self.settings.embed_color),
                ephemeral=True,
            )

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
    async def hourly_leaderboard(self) -> None:
        await self.bot.wait_until_ready()
        channel_id = self.settings.leaderboard_channel_id
        if not channel_id:
            return

        try:
            channel = await self._resolve_leaderboard_channel(channel_id)
            if channel is None:
                return

            embed = await self._build_leaderboard_embed()
            previous_message_id = await self.db.get_leaderboard_message_id(channel_id)
            if previous_message_id is not None:
                await self._delete_previous_leaderboard_message(channel, channel_id, previous_message_id)

            new_message = await channel.send(embed=embed)
            await self.db.set_leaderboard_message_id(channel_id, new_message.id)
            LOGGER.info("Updated daily leaderboard in channel %s with message %s.", channel_id, new_message.id)
        except Exception:
            LOGGER.exception("Failed to post daily leaderboard.")

    @hourly_leaderboard.before_loop
    async def before_hourly_leaderboard(self) -> None:
        await self.bot.wait_until_ready()

    async def _build_leaderboard_embed(self) -> discord.Embed:
        top_users = await self.db.get_top_users(10)
        entries: list[tuple[str, int, int]] = []
        for user in top_users:
            discord_user = self.bot.get_user(user.user_id) or await self.bot.fetch_user(user.user_id)
            entries.append((discord_user.display_name, user.level, user.xp))
        return build_leaderboard_embed(entries, self.settings.embed_color)

    async def _resolve_leaderboard_channel(
        self,
        channel_id: int,
    ) -> discord.TextChannel | discord.Thread | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)

        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            return channel

        LOGGER.warning("Configured leaderboard channel %s is not a supported text destination.", channel_id)
        return None

    async def _delete_previous_leaderboard_message(
        self,
        channel: discord.TextChannel | discord.Thread,
        channel_id: int,
        message_id: int,
    ) -> None:
        try:
            previous_message = await channel.fetch_message(message_id)
            await previous_message.delete()
            LOGGER.info("Deleted previous leaderboard message %s in channel %s.", message_id, channel_id)
        except discord.NotFound:
            LOGGER.info("Previous leaderboard message %s was already missing in channel %s.", message_id, channel_id)
        except discord.HTTPException:
            LOGGER.exception("Failed to delete previous leaderboard message %s in channel %s.", message_id, channel_id)
        finally:
            await self.db.set_leaderboard_message_id(channel_id, None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
