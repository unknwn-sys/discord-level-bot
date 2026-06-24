from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import discord
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .xp import calculate_progress


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        font_path = Path(__file__).parent.parent / "assets" / "rankcard" / "DejaVuSans.ttf"
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(start_size, min_size - 1, -2):
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return _load_font(min_size)


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    ratio: float,
    background: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
) -> None:
    x0, y0, x1, y1 = bounds
    radius = (y1 - y0) // 2
    draw.rounded_rectangle(bounds, radius=radius, fill=background)
    fill_width = x0 + int((x1 - x0) * max(0.0, min(ratio, 1.0)))
    if fill_width > x0:
        draw.rounded_rectangle((x0, y0, fill_width, y1), radius=radius, fill=fill)


def _draw_stat_box(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    label: str,
    value: str,
    accent: tuple[int, int, int, int],
) -> None:
    x0, y0, x1, y1 = bounds
    draw.rounded_rectangle(bounds, radius=20, fill=(33, 41, 58, 255), outline=(55, 67, 90, 255), width=2)
    label_font = _load_font(18)
    value_font = _fit_text(draw, value, (x1 - x0) - 28, 28, 18)
    draw.text((x0 + 16, y0 + 14), label.upper(), font=label_font, fill=(149, 161, 184, 255))
    draw.text((x0 + 16, y0 + 48), value, font=value_font, fill=accent)


def _render_rank_card(
    avatar_bytes: bytes,
    username: str,
    level: int,
    xp: int,
    rank: int | None,
    daily_xp_earned: int,
    daily_xp_cap: int,
    max_level: int,
) -> discord.File:
    width, height = 1180, 500
    card = Image.new("RGBA", (width, height), (15, 20, 30, 255))
    draw = ImageDraw.Draw(card)

    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=34, fill=(23, 30, 43, 255))
    draw.rounded_rectangle((32, 32, width - 32, height - 32), radius=28, outline=(87, 119, 255, 255), width=2)

    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((220, 220))
    avatar_mask = Image.new("L", (220, 220), 0)
    ImageDraw.Draw(avatar_mask).ellipse((0, 0, 220, 220), fill=255)
    avatar = ImageOps.fit(avatar, (220, 220))
    card.paste(avatar, (58, 82), avatar_mask)
    draw.ellipse((50, 74, 286, 310), outline=(94, 128, 255, 255), width=4)

    username = username[:32]
    username_font = _fit_text(draw, username, 500, 44, 28)
    title_font = _load_font(20)
    headline_font = _load_font(30)
    body_font = _load_font(22)
    small_font = _load_font(18)
    detail_font = _load_font(16)

    draw.text((330, 70), "COMMUNITY PROFILE", font=title_font, fill=(134, 149, 176, 255))
    draw.text((330, 102), username, font=username_font, fill=(247, 249, 252, 255))

    rank_value = f"#{rank}" if rank else "Unranked"
    level_value = "MAX LEVEL" if level >= max_level else f"Level {level}"
    _draw_stat_box(draw, (330, 156, 565, 251), "Server Rank", rank_value, (245, 247, 250, 255))
    _draw_stat_box(
        draw,
        (585, 156, 820, 251),
        "Current Level",
        level_value,
        (116, 210, 160, 255) if level >= max_level else (111, 152, 255, 255),
    )
    _draw_stat_box(draw, (840, 156, 1095, 251), "Total XP", f"{xp}", (245, 247, 250, 255))

    current_progress, needed_for_next, progress_ratio, at_max = calculate_progress(xp, max_level=max_level)
    xp_panel = (330, 286, 736, 432)
    daily_panel = (760, 286, 1095, 432)
    draw.rounded_rectangle(xp_panel, radius=24, fill=(28, 36, 52, 255), outline=(55, 67, 90, 255), width=2)
    draw.rounded_rectangle(daily_panel, radius=24, fill=(28, 36, 52, 255), outline=(55, 67, 90, 255), width=2)

    xp_section_left = xp_panel[0] + 24
    xp_section_right = xp_panel[2] - 24
    draw.text((xp_section_left, xp_panel[1] + 20), "XP Progress", font=headline_font, fill=(245, 247, 250, 255))
    progress_value = "MAX LEVEL" if at_max or level >= max_level else f"{current_progress} / {needed_for_next} XP"
    progress_value_font = _fit_text(draw, progress_value, 300, 24, 18)
    draw.text((xp_section_right, xp_panel[1] + 28), progress_value, font=progress_value_font, fill=(198, 205, 218, 255), anchor="ra")
    _draw_progress_bar(
        draw,
        (xp_section_left, xp_panel[1] + 74, xp_section_right, xp_panel[1] + 102),
        1.0 if at_max else progress_ratio,
        (42, 52, 73, 255),
        (91, 126, 255, 255),
    )
    xp_hint = "You are at the level cap." if at_max or level >= max_level else "Keep chatting to push toward the next level."
    draw.text((xp_section_left, xp_panel[1] + 118), xp_hint, font=detail_font, fill=(150, 160, 177, 255))

    daily_left = daily_panel[0] + 24
    daily_right = daily_panel[2] - 24
    draw.text((daily_left, daily_panel[1] + 20), "Daily XP", font=headline_font, fill=(245, 247, 250, 255))
    daily_value = f"{daily_xp_earned} / {daily_xp_cap}"
    daily_value_font = _fit_text(draw, daily_value, 180, 24, 18)
    draw.text((daily_right, daily_panel[1] + 28), daily_value, font=daily_value_font, fill=(196, 206, 222, 255), anchor="ra")
    daily_ratio = min(max(daily_xp_earned / max(daily_xp_cap, 1), 0.0), 1.0)
    _draw_progress_bar(
        draw,
        (daily_left, daily_panel[1] + 74, daily_right, daily_panel[1] + 102),
        daily_ratio,
        (42, 52, 73, 255),
        (116, 210, 160, 255),
    )
    daily_remaining = max(daily_xp_cap - daily_xp_earned, 0)
    draw.text((daily_left, daily_panel[1] + 118), f"{daily_remaining} XP remaining today", font=detail_font, fill=(226, 231, 239, 255))

    if at_max or level >= max_level:
        badge_bounds = (930, 76, 1098, 124)
        draw.rounded_rectangle(badge_bounds, radius=20, fill=(116, 210, 160, 255))
        badge_font = _load_font(20)
        draw.text(((badge_bounds[0] + badge_bounds[2]) // 2, 100), "MAX LEVEL", font=badge_font, fill=(18, 25, 37, 255), anchor="mm")

    buffer = BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="rankcard.png")


async def generate_rank_card(
    member: discord.abc.User,
    level: int,
    xp: int,
    rank: int | None,
    daily_xp_earned: int,
    daily_xp_cap: int,
    max_level: int,
) -> discord.File:
    avatar_bytes = await member.display_avatar.replace(size=256).read()
    return await asyncio.to_thread(
        _render_rank_card,
        avatar_bytes,
        member.display_name,
        level,
        xp,
        rank,
        daily_xp_earned,
        daily_xp_cap,
        max_level,
    )
