import logging
import traceback
from aiogram import Router, Bot
from aiogram.types import ErrorEvent
from config import settings

logger = logging.getLogger(__name__)
error_router = Router()


@error_router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot):
    """
    Catches all unhandled errors in bot handlers to prevent crashes
    and notifies admin if configured.
    """
    exception = event.exception
    update = event.update

    logger.error(f"Global Exception Handler caught error: {exception}")
    logger.error(traceback.format_exc())

    # Send warning to user if possible
    try:
        if update.message:
            await update.message.answer(
                "❌ **Kutilmagan xatolik yuz berdi.**\n"
                "Xatolik tizim jurnaliga qayd etildi. Iltimos, qaytadan urinib ko'ring yoki /start bosing."
            )
        elif update.callback_query:
            await update.callback_query.answer("❌ Kutilmagan xatolik yuz berdi!", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to respond to user after error: {e}")

    # Notify admins about critical errors
    if settings.ADMIN_IDS:
        error_msg = (
            f"🚨 <b>BOT XATOLIGI (CRITICAL ERROR)</b>\n\n"
            f"<b>Xatolik:</b> <code>{type(exception).__name__}: {str(exception)[:200]}</code>\n"
            f"<b>Update:</b> <code>{update.update_id}</code>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=error_msg, parse_mode="HTML")
            except Exception:
                pass
