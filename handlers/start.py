from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_helper import get_or_create_user, seed_default_categories
from config import settings

start_router = Router()


def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Xarajat Qo'shish"), KeyboardButton(text="💰 Kirim Qo'shish")],
        [KeyboardButton(text="📋 Xarajatlar (Ro'yxat & CRUD)"), KeyboardButton(text="💳 Mening Balansim")],
        [KeyboardButton(text="📊 Grafik Tahlil"), KeyboardButton(text="📁 Excel (Eksport & Import)")],
        [KeyboardButton(text="⚙️ Sozlamalar (Eslatma)")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="👑 Admin Panel")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


@start_router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )
    await seed_default_categories(session)

    is_admin = settings.is_admin(user.telegram_id)
    welcome_text = (
        f"👋 <b>Assalomu alaykum, {message.from_user.full_name}!</b>\n\n"
        f"<b>Moliya & Xarajatlar Boshqaruvi Botiga</b> xush kelibsiz.\n\n"
        f"Ushbu bot yordamida siz:\n"
        f"• Daily/Kunlik xarajatlaringizni tez va qulay kiritishingiz,\n"
        f"• Visual diagrammalar (grafik tahlil) olishingiz,\n"
        f"• Hisobotlarni <b>Excel</b> formatida yuklab olishingiz va Excel'dan ma'lumot kiritishingiz,\n"
        f"• Kun oxirida qolgan xarajatlar bo'yicha eslatmalarni sozlamasini boshqarishingiz mumkin.\n\n"
        f"<i>Boshlash uchun quyidagi menyu tugmalaridan birini tanlang:</i>"
    )

    await message.answer(
        text=welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(is_admin)
    )
