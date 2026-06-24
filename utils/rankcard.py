from __future__ import annotations

from io import BytesIO

import discord
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .xp import calculate_progress


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


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


async def generate_rank_card(
    member: discord.abc.User,
    level: int,
    xp: int,
    rank: int | None,
    daily_xp_earned: int,
    daily_xp_cap: int,
    max_level: int,
) -> discord.File:
    width, height = 980, 320
    card = Image.new("RGBA", (width, height), (18, 23, 33, 255))
    draw = ImageDraw.Draw(card)

    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=28, fill=(29, 36, 51, 255))
    draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=24, outline=(92, 126, 255, 255), width=2)

    avatar_bytes = await member.display_avatar.replace(size=256).read()
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((170, 170))
    avatar_mask = Image.new("L", (170, 170), 0)
    ImageDraw.Draw(avatar_mask).ellipse((0, 0, 170, 170), fill=255)
    avatar = ImageOps.fit(avatar, (170, 170))
    card.paste(avatar, (52, 72), avatar_mask)

    title_font = _load_font(36)
    section_font = _load_font(24)
    body_font = _load_font(22)
    small_font = _load_font(18)

    draw.text((260, 56), member.display_name[:26], font=title_font, fill=(245, 247, 250, 255))
    rank_text = f"Server Rank #{rank}" if rank else "Server Rank Unranked"
    draw.text((260, 102), rank_text, font=section_font, fill=(189, 197, 212, 255))

    maxed = level >= max_level and xp >= 0
    level_text = f"Level {level}" if level < max_level else "MAX LEVEL"
    draw.text((260, 142), level_text, font=section_font, fill=(116, 210, 160, 255) if maxed else (112, 150, 255, 255))
    draw.text((260, 178), f"Total XP {xp}", font=body_font, fill=(229, 233, 240, 255))

    current_progress, needed_for_next, progress_ratio, at_max = calculate_progress(xp, max_level=max_level)
    progress_label = "XP Progress"
    progress_text = "MAX LEVEL" if at_max or level >= max_level else f"{current_progress} / {needed_for_next} XP"
    draw.text((260, 218), progress_label, font=small_font, fill=(169, 179, 198, 255))
    draw.text((740, 218), progress_text, font=small_font, fill=(245, 247, 250, 255), anchor="ra")
    _draw_progress_bar(draw, (260, 246, 744, 270), 1.0 if at_max else progress_ratio, (54, 63, 83, 255), (92, 126, 255, 255))

    daily_ratio = min(max(daily_xp_earned / max(daily_xp_cap, 1), 0.0), 1.0)
    draw.text((770, 86), "Daily XP", font=section_font, fill=(245, 247, 250, 255))
    draw.text((770, 122), f"{daily_xp_earned} / {daily_xp_cap}", font=body_font, fill=(205, 213, 225, 255))
    _draw_progress_bar(draw, (770, 160, 920, 182), daily_ratio, (54, 63, 83, 255), (116, 210, 160, 255))
    draw.text((770, 200), "Message XP progress resets at midnight UTC", font=small_font, fill=(156, 163, 175, 255))

    if at_max or level >= max_level:
        draw.rounded_rectangle((770, 228, 920, 268), radius=18, fill=(116, 210, 160, 255))
        draw.text((845, 248), "MAX LEVEL", font=small_font, fill=(20, 27, 38, 255), anchor="mm")

    buffer = BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(fp=buffer, filename="rankcard.png")
