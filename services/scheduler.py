import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.base import AsyncSessionLocal
from database.db_helper import get_active_reminder_users

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def check_and_send_daily_reminders(bot: Bot):
    """
    Checks active users whose reminder_time matches current time (HH:MM)
    and sends a reminder message.
    """
    now_time_str = datetime.now().strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        try:
            users = await get_active_reminder_users(session)
            for user in users:
                if user.reminder_time == now_time_str:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="➕ Xarajat Qo'shish", callback_data="add_expense_start"),
                            InlineKeyboardButton(text="✅ Barchasi Kiritilgan", callback_data="reminder_done")
                        ]
                    ])
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=(
                                "🔔 <b>Kunlik Xarajatlar Eslatmasi!</b>\n\n"
                                "Assalomu alaykum! Bugun qilgan barcha xarajatlaringizni botga kiritdingizmi?\n"
                                "Hech qanday xarajat qolib ketmaganini tekshiring."
                            ),
                            parse_mode="HTML",
                            reply_markup=kb
                        )
                        logger.info(f"Daily reminder sent to user {user.telegram_id}")
                    except Exception as e:
                        logger.warning(f"Failed to send reminder to user {user.telegram_id}: {e}")
        except Exception as e:
            logger.error(f"Error in daily reminder job: {e}")


def setup_scheduler(bot: Bot):
    """
    Starts APScheduler and registers cron/interval jobs.
    """
    # Check every minute for matching HH:MM
    scheduler.add_job(
        check_and_send_daily_reminders,
        trigger="cron",
        minute="*",
        args=[bot],
        id="daily_reminder_job",
        replace_existing=True
    )
    scheduler.start()
    logger.info("APScheduler started successfully.")
