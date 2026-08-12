from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_helper import get_or_create_user, update_user_reminder

from aiogram.filters import StateFilter

settings_router = Router()


class SettingsState(StatesGroup):
    enter_reminder_time = State()


@settings_router.message(F.text == "⚙️ Sozlamalar (Eslatma)", StateFilter("*"))
@settings_router.callback_query(F.data == "reminder_done")
async def show_settings(event: Message | CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    user = await get_or_create_user(session, user_id, event.from_user.full_name, event.from_user.username)

    status_str = "🟢 Yoqilgan" if user.is_reminder_active else "🔴 O'chirilgan"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔴 O'chirish" if user.is_reminder_active else "🟢 Yoqish",
                callback_data="toggle_reminder"
            ),
            InlineKeyboardButton(text="🕒 Vaqtni O'zgartirish", callback_data="change_reminder_time")
        ]
    ])

    text = (
        f"⚙️ <b>Kunlik Eslatma Sozlamalari:</b>\n\n"
        f"🔔 <b>Status:</b> {status_str}\n"
        f"⏰ <b>Eslatish vaqti:</b> <code>{user.reminder_time}</code>\n\n"
        f"<i>Bot har kuni belgilangan vaqtda xarajatlarni kiritishni eslatib so'rov yuboradi.</i>"
    )

    if isinstance(event, CallbackQuery):
        await event.answer("Rahmat, eslatma qabul qilindi!", show_alert=True)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@settings_router.callback_query(F.data == "toggle_reminder")
async def toggle_reminder(call: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, call.from_user.id, call.from_user.full_name, call.from_user.username)
    new_status = not user.is_reminder_active

    await update_user_reminder(session, call.from_user.id, user.reminder_time, new_status)
    await call.answer(f"Eslatma {'yoqildi' if new_status else 'o\'chirildi'}.", show_alert=True)

    status_str = "🟢 Yoqilgan" if new_status else "🔴 O'chirilgan"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔴 O'chirish" if new_status else "🟢 Yoqish",
                callback_data="toggle_reminder"
            ),
            InlineKeyboardButton(text="🕒 Vaqtni O'zgartirish", callback_data="change_reminder_time")
        ]
    ])
    text = (
        f"⚙️ <b>Kunlik Eslatma Sozlamalari:</b>\n\n"
        f"🔔 <b>Status:</b> {status_str}\n"
        f"⏰ <b>Eslatish vaqti:</b> <code>{user.reminder_time}</code>\n\n"
        f"<i>Bot har kuni belgilangan vaqtda xarajatlarni kiritishni eslatib so'rov yuboradi.</i>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@settings_router.callback_query(F.data == "change_reminder_time")
async def start_change_time(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(SettingsState.enter_reminder_time)
    await call.message.answer(
        "🕒 <b>Kunlik eslatish vaqtini kiriting (HH:MM formatida):</b>\n"
        "<i>Masalan: 21:00 yoki 20:30</i>",
        parse_mode="HTML"
    )


@settings_router.message(SettingsState.enter_reminder_time)
async def process_reminder_time(message: Message, state: FSMContext, session: AsyncSession):
    time_str = message.text.strip()
    import re
    if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time_str):
        await message.answer("❌ Noto'g'ri vaqt formati! HH:MM shaklida kiriting (Masalan: 21:30):")
        return

    # Normalize format e.g. 9:00 -> 09:00
    parts = time_str.split(":")
    normalized = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

    await update_user_reminder(session, message.from_user.id, normalized, True)
    await state.clear()

    await message.answer(
        f"✅ <b>Eslatma vaqti muvaffaqiyatli saqlandi!</b>\n"
        f"Endi har kuni soat <code>{normalized}</code> da bot eslatma yuboradi.",
        parse_mode="HTML"
    )
