from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_helper import get_user_balance_summary, update_wallet_balance
from services.amount_parser import parse_amount, AMOUNT_HINT

wallet_router = Router()

class WalletState(StatesGroup):
    enter_balance = State()


def fmt(amount: float | None) -> str:
    if amount is None:
        return "Noma'lum"
    return f"{amount:,.0f}".replace(",", " ")


from aiogram.filters import StateFilter

@wallet_router.message(F.text == "💳 Mening Balansim", StateFilter("*"))
async def show_wallet_balance(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    summary = await get_user_balance_summary(session, message.from_user.id)
    
    wallet = summary["wallet"]
    total_income = summary.get("total_income", 0.0)
    total_spent = summary["total_spent"]
    remaining = summary["remaining"]

    if wallet is None and total_income == 0.0:
        text = (
            "🏦 <b>Sizning balansingiz (Boshlang'ich summa) kiritilmagan.</b>\n\n"
            f"🟢 <b>Jami Kirimlar:</b> {fmt(total_income)} so'm\n"
            f"🔴 <b>Jami Xarajatlar:</b> {fmt(total_spent)} so'm\n\n"
            "<i>Aniq qoldiqni ko'rish uchun, iltimos balansingizni (o'zingizdagi bor pulni) kiriting.</i>"
        )
    else:
        wallet_str = f"{fmt(wallet)} so'm" if wallet is not None else "0 so'm"
        text = (
            "🏦 <b>Sizning Balansingiz:</b>\n\n"
            f"💵 <b>Boshlang'ich summa:</b> {wallet_str}\n"
            f"🟢 <b>Jami Kirimlar:</b> {fmt(total_income)} so'm\n"
            f"🔴 <b>Jami Xarajatlar:</b> {fmt(total_spent)} so'm\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 <b>QOLGAN MABLAG':</b> <b>{fmt(remaining)} so'm</b>"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Balansni kiritish / O'zgartirish", callback_data="edit_wallet_balance")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@wallet_router.callback_query(F.data == "edit_wallet_balance")
async def edit_wallet_balance_prompt(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(
        f"💵 <b>O'zingizda bor aniq summani kiriting:</b>\n{AMOUNT_HINT}",
        parse_mode="HTML"
    )
    await state.set_state(WalletState.enter_balance)


@wallet_router.message(WalletState.enter_balance)
async def process_wallet_balance(message: Message, state: FSMContext, session: AsyncSession):
    from handlers.expense_crud import MENU_BUTTONS
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return

    amount = parse_amount(text_val)
    if amount is None:
        await message.answer(
            f"❌ Noto'g'ri summa kiritildi. Quyidagi formatlardan birida kiriting:\n{AMOUNT_HINT}",
            parse_mode="HTML"
        )
        return
    
    await update_wallet_balance(session, message.from_user.id, amount)
    await state.clear()
    
    # Show updated balance
    await show_wallet_balance(message, session, state)
