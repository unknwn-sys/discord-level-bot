from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from config import Settings, get_settings
from database import Database

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class CommunityBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True

        super().__init__(command_prefix=settings.command_prefix, intents=intents)
        self.settings = settings
        self.db = Database(settings.database_url)
        self.logger = logging.getLogger("discord_level_bot")

    async def setup_hook(self) -> None:
        self.logger.info("Starting bot setup.")
        await self.db.connect()
        await self.db.initialize()

        for extension in ("cogs.leveling", "cogs.leaderboard", "cogs.profile", "cogs.rewards"):
            await self.load_extension(extension)
            self.logger.info("Loaded extension %s.", extension)

        synced_commands = await self.tree.sync()
        self.logger.info("Synced %s application commands.", len(synced_commands))

    async def close(self) -> None:
        self.logger.info("Shutting down bot.")
        await self.db.close()
        await super().close()

    async def on_ready(self) -> None:
        self.logger.info("Bot ready as %s (%s).", self.user, self.user.id if self.user else "unknown")
        if self.settings.bot_commands_channel_id:
            self.logger.info("Level-up announcement channel configured: %s.", self.settings.bot_commands_channel_id)
        if self.settings.leaderboard_channel_id:
            self.logger.info("Hourly leaderboard channel configured: %s.", self.settings.leaderboard_channel_id)

    async def on_command_error(self, context: commands.Context, exception: commands.CommandError) -> None:
        self.logger.exception("Command error in %s.", context.command, exc_info=exception)


async def main() -> None:
    configure_logging()
    settings = get_settings()
    bot = CommunityBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
