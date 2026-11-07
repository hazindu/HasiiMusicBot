# ==============================================================================
# _thumbnails.py - Thumbnails
# ==============================================================================
# Generates the frosted glass "Now Playing" thumbnails using PIL.
# Runs in a separate thread so it doesn't block the main asyncio loop.
# ==============================================================================

import os
import re
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from HasiiMusic import config
from HasiiMusic.helpers import Track

# Modern frosted glass design constants
PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 170

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + 36

TITLE_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


class Thumbnail:
    def __init__(self):
        try:
            self.title_font = ImageFont.truetype(
                "HasiiMusic/helpers/Raleway-Bold.ttf", 32)
            self.regular_font = ImageFont.truetype(
                "HasiiMusic/helpers/Inter-Light.ttf", 18)
        except OSError:
            self.title_font = self.regular_font = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
            return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            thumb_url = getattr(song, "thumbnail", "")
            if not thumb_url:
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", song.id):
                    thumb_url = f"https://i.ytimg.com/vi/{song.id}/hqdefault.jpg"
                else:
                    return config.DEFAULT_THUMB

            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', song.id)[:40]
            temp = f"cache/temp_{safe_id}.jpg"
            output = f"cache/{safe_id}_modern.png"
            if os.path.exists(output):
                return output

            # Download thumbnail (async operation)
            await self.save_thumb(temp, thumb_url)
            
            # run PIL in a thread so it doesn't block the event loop
            return await asyncio.get_event_loop().run_in_executor(
                None, self._generate_sync, temp, output, song, size
            )
        except Exception:
            return config.DEFAULT_THUMB

    def _generate_sync(self, temp: str, output: str, song: Track, size=(1280, 720)) -> str:
        try:
            # Prepare base image
            with Image.open(temp) as temp_img:
                base = temp_img.resize(size).convert("RGBA")

            # Create blurred background
            bg = ImageEnhance.Brightness(base.filter(
                ImageFilter.BoxBlur(10))).enhance(0.6)

            # Create frosted glass panel
            panel_area = bg.crop(
                (PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
            overlay = Image.new("RGBA", (PANEL_W, PANEL_H),
                                (255, 255, 255, TRANSPARENCY))
            frosted = Image.alpha_composite(panel_area, overlay)

            # Apply rounded corners to panel
            mask = Image.new("L", (PANEL_W, PANEL_H), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, PANEL_W, PANEL_H), 50, fill=255)
            bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

            # Add thumbnail with rounded corners
            thumb = base.resize((THUMB_W, THUMB_H))
            tmask = Image.new("L", thumb.size, 0)
            ImageDraw.Draw(tmask).rounded_rectangle(
                (0, 0, THUMB_W, THUMB_H), 20, fill=255)
            bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

            # Draw text elements
            draw = ImageDraw.Draw(bg)

            # Clean and display title
            clean_title = re.sub(r"\W+", " ", song.title).title()
            draw.text(
                (TITLE_X, TITLE_Y),
                trim_to_width(clean_title, self.title_font, MAX_TITLE_WIDTH),
                fill="black",
                font=self.title_font
            )

            # Metadata
            draw.text(
                (TITLE_X, META_Y),
                f"YouTube | {song.view_count or 'Unknown Views'}",
                fill="black",
                font=self.regular_font
            )

            # Progress bar
            draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)],
                      fill="red", width=6)
            draw.line([(BAR_X + BAR_RED_LEN, BAR_Y),
                      (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
            draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7),
                         (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

            # Time labels
            draw.text((BAR_X, BAR_Y + 15), "00:00",
                      fill="black", font=self.regular_font)

            is_live = getattr(song, 'is_live', False)
            end_text = "Live" if is_live else song.duration
            draw.text(
                (BAR_X + BAR_TOTAL_LEN - (90 if is_live else 60), BAR_Y + 15),
                end_text,
                fill="red" if is_live else "black",
                font=self.regular_font
            )

            # Control icons (if available)
            icons_path = "HasiiMusic/helpers/play_icons.png"
            if os.path.isfile(icons_path):
                with Image.open(icons_path) as icons_img:
                    ic = icons_img.resize((ICONS_W, ICONS_H)).convert("RGBA")
                    r, g, b, a = ic.split()
                    black_ic = Image.merge(
                        "RGBA", (r.point(lambda _: 0), g.point(lambda _: 0), b.point(lambda _: 0), a))
                    bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

            # Save and cleanup
            bg.save(output)
            try:
                os.remove(temp)
            except OSError:
                pass

            return output
        except Exception:
            return config.DEFAULT_THUMB
