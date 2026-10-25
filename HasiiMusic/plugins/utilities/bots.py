# ==============================================================================
# bots.py - Bot Scanner
# ==============================================================================
# Command to scan and list all bots currently residing in the group.
# ==============================================================================

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMembersFilter, ParseMode
from HasiiMusic import app, lang

@app.on_message(filters.command("bots") & filters.group)
@lang.language()
async def list_bots(client, message: Message):
    # Auto-delete command message
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        bot_list = []
        bot_count = 0
        
        # Send initial message
        status_msg = await message.reply_text(message.lang["bots_scanning"], parse_mode=ParseMode.HTML)
        
        # Iterate through all members and filter bots
        async for member in client.get_chat_members(message.chat.id, filter=ChatMembersFilter.BOTS):
            bot_count += 1
            bot_username = f"@{member.user.username}" if member.user.username else "No Username"
            bot_list.append(f"{bot_count}. <a href='tg://user?id={member.user.id}'>{member.user.first_name}</a> - {bot_username}")
        
        if bot_count == 0:
            await status_msg.edit_text(message.lang["bots_none"], parse_mode=ParseMode.HTML)
            return
        
        # Format the response
        response = message.lang["bots_title"].format(message.chat.title)
        response += "<blockquote>" + "\n".join(bot_list) + "</blockquote>"
        response += message.lang["bots_total"].format(bot_count)
        
        await status_msg.edit_text(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        if "FLOOD_WAIT" not in str(e):
            try:
                await message.reply_text(message.lang["bots_error"].format(str(e)), parse_mode=ParseMode.HTML)
            except:
                pass
