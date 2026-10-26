# ==============================================================================
# stats.py - Sudo Stats
# ==============================================================================
# Deep dive into bot and system statistics.
# ==============================================================================

# Copyright (c) 2025 Hasindu Nagolla
# Licensed under the MIT License.
# This file is part of ˹ʜᴀꜱɪɪ ᴍᴜꜱɪᴄ˼


import os
import platform
import sys

import psutil
from pyrogram import __version__, filters, types
from pytgcalls import __version__ as pytgver

from HasiiMusic import app, config, db, lang, userbot
from HasiiMusic.plugins import all_modules


@app.on_message(filters.command(["stats"]) & ~app.bl_users)
@lang.language()
async def _stats(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    sent = await m.reply_photo(
        photo=config.PING_IMG,
        caption=m.lang["stats_fetching"],
    )

    # from_user is None for anonymous admins and channel posts
    is_sudo = bool(m.from_user) and m.from_user.id in app.sudoers

    _utext = m.lang["stats_user"].format(
        app.name,
        len(userbot.clients),
        config.AUTO_LEAVE,
        len(db.blacklisted),
        len(app.bl_users),
        len(app.sudoers),
        len(await db.get_chats()),
        len(await db.get_users()),
    )
    
    # Add system stats for sudo users only
    if is_sudo:
        pid = os.getpid()
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_count = psutil.cpu_count()
        
        mem = psutil.virtual_memory()
        used_mem = round(mem.used / (1024 ** 3), 2)
        total_mem = round(mem.total / (1024 ** 3), 2)
        
        disk = psutil.disk_usage("/")
        used_disk = round(disk.used / (1024 ** 3), 2)
        total_disk = round(disk.total / (1024 ** 3), 2)

        _utext += m.lang["stats_sudo"].format(
            len(all_modules),
            platform.system(),
            f"{used_mem}GB | {total_mem}GB",
            f"{cpu_percent}% ({cpu_count} cores)",
            f"{used_disk}GB | {total_disk}GB",
            sys.version.split()[0],
            __version__,
            pytgver,
        )
    
    await sent.edit_caption(_utext)
