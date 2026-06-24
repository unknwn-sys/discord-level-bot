from __future__ import annotations

import logging
import re

import discord
from discord.ext import commands, tasks

from config import Settings
from database import Database, MessageXpResult
from utils import (
    CooldownManager,
    build_daily_cap_embed,
    build_level_up_embed,
    calculate_level,
    calculate_progress,
    calculate_required_xp,
    get_message_xp,
)

LOGGER = logging.getLogger(__name__)


def _normalize_message(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())


class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.settings: Settings = bot.settings  # type: ignore[attr-defined]
        self.cooldowns = CooldownManager(self.settings.xp_cooldown)
        self.voice_xp_loop.change_interval(minutes=self.settings.voice_xp_interval_minutes)
        self.voice_xp_loop.start()

    def cog_unload(self) -> None:
        self.voice_xp_loop.cancel()

    @property
    def max_xp(self) -> int:
        return calculate_required_xp(self.settings.max_level)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        if not content or len(content) < 5:
            return

        normalized = _normalize_message(content)
        try:
            user = await self.db.get_or_create_user(message.author.id)
            if user.last_message and normalized == user.last_message:
                return
            if self.cooldowns.is_on_cooldown(message.author.id):
                await self.db.set_last_message(message.author.id, normalized)
                return

            xp_gain = get_message_xp(user.level)
            result = await self.db.apply_message_xp(
                message.author.id,
                raw_xp_gain=xp_gain,
                content=normalized,
                daily_cap=self.settings.daily_xp_cap,
                max_xp=self.max_xp,
                max_level=self.settings.max_level,
            )
            self.cooldowns.touch(message.author.id)

            if result.xp_awarded > 0:
                LOGGER.info("Awarded %s XP to %s from message activity.", result.xp_awarded, message.author.id)

            if result.level_up:
                await self._handle_level_up(message.author, message.guild, result)
            elif result.reached_daily_cap:
                LOGGER.info("User %s reached the daily message XP cap.", message.author.id)
                await message.channel.send(embed=build_daily_cap_embed(self.settings.daily_xp_cap, self.settings.embed_color))

            if result.reached_max_level:
                LOGGER.info("User %s reached level 50 or the XP cap.", message.author.id)
        except Exception:
            LOGGER.exception("Failed to process message XP for user %s.", message.author.id)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return
        if before.channel != after.channel:
            await self.db.get_or_create_user(member.id)

    @tasks.loop(minutes=5)
    async def voice_xp_loop(self) -> None:
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                eligible_members = [
                    member
                    for member in channel.members
                    if not member.bot
                    and member.voice is not None
                    and not member.voice.self_mute
                    and not member.voice.self_deaf
                    and not member.voice.mute
                    and not member.voice.deaf
                ]
                if len(eligible_members) < 2:
                    continue

                for member in eligible_members:
                    try:
                        user = await self.db.get_or_create_user(member.id)
                        if user.level >= self.settings.max_level or user.xp >= self.max_xp:
                            continue

                        xp_gain = min(self.settings.voice_xp_reward, max(0, self.max_xp - user.xp))
                        new_total_xp = user.xp + xp_gain
                        new_level = calculate_level(new_total_xp, max_level=self.settings.max_level)
                        await self.db.update_voice_time(
                            member.id,
                            self.settings.voice_xp_interval_minutes,
                            xp_delta=xp_gain,
                            new_level=new_level,
                        )
                        if new_level > user.level:
                            result = MessageXpResult(
                                xp_awarded=xp_gain,
                                total_xp=new_total_xp,
                                new_level=new_level,
                                daily_xp_earned=user.daily_xp_earned,
                                daily_xp_remaining=max(0, self.settings.daily_xp_cap - user.daily_xp_earned),
                                level_up=True,
                                reached_daily_cap=False,
                                already_capped=False,
                                reached_max_level=new_level >= self.settings.max_level or new_total_xp >= self.max_xp,
                            )
                            await self._handle_level_up(member, guild, result)
                            if result.reached_max_level:
                                LOGGER.info("User %s reached level 50 through voice XP.", member.id)
                    except Exception:
                        LOGGER.exception("Failed to award voice XP to user %s.", member.id)

    @voice_xp_loop.before_loop
    async def before_voice_xp_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def _handle_level_up(
        self,
        member: discord.abc.User,
        guild: discord.Guild,
        result: MessageXpResult,
    ) -> None:
        LOGGER.info("User %s leveled up to %s.", member.id, result.new_level)
        reward_name = self.settings.role_rewards.get(result.new_level)
        if reward_name and isinstance(member, discord.Member):
            role = discord.utils.get(guild.roles, name=reward_name)
            if role is not None:
                try:
                    await member.add_roles(role, reason=f"Reached level {result.new_level}")
                except discord.HTTPException:
                    LOGGER.exception("Failed to assign role %s to %s.", reward_name, member.id)

        try:
            rank = await self.db.get_rank(member.id)
            _, _, progress_ratio, at_max = calculate_progress(result.total_xp, max_level=self.settings.max_level)
            embed = build_level_up_embed(
                member,
                result.new_level,
                result.total_xp,
                rank,
                int(progress_ratio * 100),
                self.settings.max_level,
                self.settings.embed_color,
            )
            channel_id = self.settings.bot_commands_channel_id
            destination = guild.get_channel(channel_id) if channel_id is not None else None
            if destination is None and channel_id is not None:
                destination = await self.bot.fetch_channel(channel_id)

            if destination is None:
                LOGGER.warning("No bot commands channel configured for level-up announcements in guild %s.", guild.id)
                return

            await destination.send(f"🎉 {member.name} upgraded to level {result.new_level}!")
            await destination.send(embed=embed)
            if at_max or result.reached_max_level:
                LOGGER.info("User %s reached level 50.", member.id)
        except discord.HTTPException:
            LOGGER.exception("Failed to announce level up for %s.", member.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LevelingCog(bot))
