# ==============================================================================
# __main__.py - Entry Point
# ==============================================================================
# Bootstraps the bot: connects to Mongo, starts the client and assistants, 
# loads plugins, and idles until killed.
# ==============================================================================

import asyncio
import importlib
import sys
from pyrogram import idle

# Raise the file descriptor limit on Linux to avoid "[Errno 24] Too many open files"
# when serving many groups concurrently (each audio stream + ffmpeg probe opens FDs).
if sys.platform != "win32":
    try:
        import resource
        _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        _target = min(65536, _hard)
        if _soft < _target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (_target, _hard))
    except Exception:
        pass

from HasiiMusic import (tune, app, config, db,
                   configure_asyncio_exception_handler, logger, stop, userbot, yt)
from HasiiMusic.plugins import all_modules


async def main():
    configure_asyncio_exception_handler()

    try:
        # Connect to DB
        await db.connect()
        
        # Start the main bot client
        await app.boot()
        
        # Start assistant/userbot clients
        await userbot.boot()
        
        # Initialize voice call handler
        await tune.boot()

        # Load all plugins
        for module in all_modules:
            try:
                importlib.import_module(f"HasiiMusic.plugins.{module}")
            except Exception as e:
                logger.error(f"Failed to load plugin {module}: {e}", exc_info=True)
        logger.info(f"🔌 Loaded {len(all_modules)} plugin modules.")

        # Download YouTube cookies if provided
        if config.COOKIES_URL:
            try:
                await yt.save_cookies(config.COOKIES_URL)
            except Exception as e:
                logger.error(f"Failed to download cookies: {e}")

        # Report YouTube anti-bot setup (proxy + PO token provider)
        if config.YT_PROXY:
            logger.info(f"🌐 yt-dlp proxy enabled: {config.YT_PROXY}")
        if config.POT_PROVIDER_URL:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        config.POT_PROVIDER_URL.rstrip("/") + "/ping",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            logger.info("🛡️ PO token provider reachable.")
                        else:
                            logger.warning(f"⚠️ PO token provider returned HTTP {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ PO token provider not reachable at {config.POT_PROVIDER_URL}: {e}")

        # Load sudoers and blacklisted users
        sudoers = await db.get_sudoers()
        app.sudoers.update(sudoers)
        app.sudo_filter.update(sudoers)
        app.bl_users.update(await db.get_blacklisted())
        logger.info(f"👑 Loaded {len(app.sudoers)} sudo users.")
        logger.info("\n🎉 Bot started successfully! Ready to play music! 🎵\n")

        # Keep running until Ctrl+C
        try:
            await idle()
        except KeyboardInterrupt:
            logger.info("Received stop signal...")
        except Exception as e:
            logger.error(f"Error during idle: {e}", exc_info=True)
        
        # Cleanup
        await stop()
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except SystemExit as e:
        logger.error(f"Bot exited with system error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error caused bot to stop: {e}", exc_info=True)
        # Don't raise - allow clean shutdown
