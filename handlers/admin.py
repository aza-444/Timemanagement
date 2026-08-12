from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_helper import get_admin_stats
from config import settings

admin_router = Router()


@admin_router.message(F.text == "👑 Admin Panel")
async def show_admin_panel(message: Message, session: AsyncSession):
    if not settings.is_admin(message.from_user.id):
        await message.answer("⛔ Siz administrator emassiz!")
        return

    stats = await get_admin_stats(session)

    text = (
        f"👑 <b>ADMINISTRATOR PANELI</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar soni:</b> {stats['user_count']} ta\n"
        f"📝 <b>Jami xarajat tranzaksiyalari:</b> {stats['expense_count']} ta\n"
        f"💰 <b>Tizim bo'yicha jami xarajat:</b> {stats['total_amount']:,.0f} so'm\n\n"
        f"🛡 <i>Tizim normal holatda ishlamoqda. SQLite WAL mode faol.</i>"
    )

    await message.answer(text, parse_mode="HTML")
