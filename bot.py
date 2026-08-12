import asyncio
import logging
import signal
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select

from config import settings
from database.base import init_db, AsyncSessionLocal
from database.db_helper import seed_default_categories
from database.models import User
from middlewares.db_middleware import DatabaseMiddleware
from middlewares.error_middleware import error_router
from handlers import main_router
from services.scheduler import setup_scheduler, scheduler


def configure_logging():
    log_formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
    )

    file_handler = RotatingFileHandler(
        "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


async def _broadcast(bot: Bot, text: str):
    """Send a message to ALL registered users, silently skip blocked/deleted accounts."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User))
            users = result.scalars().all()
        except Exception as e:
            logging.warning(f"Broadcast: could not load users: {e}")
            return

    sent, skipped = 0, 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            skipped += 1

    logging.info(f"Broadcast done. Sent: {sent}, Skipped (blocked/deleted): {skipped}")


async def on_startup(bot: Bot):
    logging.info("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        await seed_default_categories(session)

    setup_scheduler(bot)
    bot_info = await bot.get_me()
    logging.info(f"Bot started successfully! Username: @{bot_info.username} (ID: {bot_info.id})")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    asyncio.create_task(_broadcast(
        bot,
        f"✅ <b>Bot qayta ishga tushdi!</b>\n"
        f"⏰ Vaqt: <code>{now}</code>\n"
        f"Barcha funksiyalar normal ishlayapti. "
        f"Davom etish uchun /start ni bosing."
    ))


async def on_shutdown(bot: Bot):
    logging.info("Shutting down bot...")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        await asyncio.wait_for(_broadcast(
            bot,
            f"🔴 <b>Bot vaqtincha to'xtayapti.</b>\n"
            f"⏰ Vaqt: <code>{now}</code>\n"
            f"<i>Texnik ishlar yoki server qayta yuklanmoqda. "
            f"Bot tez orada avtomatik qayta ishga tushadi.</i>"
        ), timeout=3.0)
    except Exception:
        pass

    if scheduler.running:
        scheduler.shutdown(wait=False)
    await bot.session.close()
    logging.info("Bot stopped gracefully.")


async def main():
    configure_logging()

    if not settings.BOT_TOKEN or "ABCdefGHI" in settings.BOT_TOKEN:
        logging.error("BOT_TOKEN tozalanmagan yoki noto'g'ri! .env faylini to'g'irlang.")

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register Middlewares
    dp.update.outer_middleware(DatabaseMiddleware())

    # Include Routers
    dp.include_router(error_router)
    dp.include_router(main_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Graceful shutdown signals
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(dp.stop_polling()))
        except NotImplementedError:
            # Windows platform compatibility
            pass

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logging.critical(f"Critical unhandled exception in main polling loop: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
