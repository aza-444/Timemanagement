from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_helper import get_expenses, get_user_categories, add_expense
from services.excel_service import (
    generate_expenses_excel,
    create_sample_excel_template,
    parse_and_validate_excel
)

from aiogram.filters import StateFilter

excel_router = Router()


class ExcelImportState(StatesGroup):
    waiting_for_file = State()


@excel_router.message(F.text == "📁 Excel (Eksport & Import)", StateFilter("*"))
async def show_excel_menu(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Excel Xisobotini Yuklash (Export)", callback_data="excel_export")],
        [InlineKeyboardButton(text="📑 Import uchun Namuna Fayl (Template)", callback_data="excel_template")],
        [InlineKeyboardButton(text="📤 Excel Fayldan Bazaga Yuklash (Import)", callback_data="excel_import_start")]
    ])

    await message.answer(
        "📁 <b>Excel bilan ishlash bo'limi:</b>\n\n"
        "1. <b>Export:</b> Barcha xarajatlaringizni Excel (.xlsx) formatida yuklab olasiz.\n"
        "2. <b>Template:</b> Excel yordamida ommaviy xarajat kiritish uchun namuna shabloni.\n"
        "3. <b>Import:</b> Tayyorlagan Excel faylingizni botga yuborib avtomatik bazaga kiritasiz.",
        parse_mode="HTML",
        reply_markup=kb
    )


@excel_router.callback_query(F.data == "excel_export")
async def export_expenses_excel(call: CallbackQuery, session: AsyncSession):
    user_id = call.from_user.id
    expenses_data = await get_expenses(session, user_id)

    if not expenses_data:
        await call.answer("📭 Sizda yuklab olish uchun xarajatlar mavjud emas.", show_alert=True)
        return

    await call.answer("📥 Excel fayl shakllantirilmoqda...")

    excel_buf = generate_expenses_excel(expenses_data)
    file = BufferedInputFile(excel_buf.getvalue(), filename=f"Xarajatlar_{call.from_user.username or user_id}.xlsx")

    await call.message.answer_document(
        document=file,
        caption="📄 <b>Sizning barcha xarajatlaringiz Excel fayli:</b>",
        parse_mode="HTML"
    )


@excel_router.callback_query(F.data == "excel_template")
async def send_excel_template(call: CallbackQuery):
    await call.answer()
    template_buf = create_sample_excel_template()
    file = BufferedInputFile(template_buf.getvalue(), filename="Xarajatlar_Import_Namuna.xlsx")

    await call.message.answer_document(
        document=file,
        caption=(
            "📑 <b>Excel Import uchun Namuna Fayli!</b>\n\n"
            "Ushbu fayl modelidan foydalanib xarajatlaringizni to'ldiring hamda botga yuboring.\n"
            "<b>Ustunlar:</b> Sana (YYYY-MM-DD), Kategoriya, Summa, Izoh"
        ),
        parse_mode="HTML"
    )


@excel_router.callback_query(F.data == "excel_import_start")
async def start_excel_import(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(ExcelImportState.waiting_for_file)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_excel_import")]
    ])

    await call.message.answer(
        "📤 <b>Excel (.xlsx) faylini botga yuboring:</b>\n\n"
        "Faylingizda <code>Sana</code>, <code>Kategoriya</code> va <code>Summa</code> ustunlari bo'lishi shart.",
        parse_mode="HTML",
        reply_markup=kb
    )


@excel_router.callback_query(F.data == "cancel_excel_import", ExcelImportState.waiting_for_file)
async def cancel_excel_import(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Import bekor qilindi.")
    await call.message.answer("❌ Excel import bekor qilindi.")


@excel_router.message(ExcelImportState.waiting_for_file, F.document)
async def process_excel_document(message: Message, state: FSMContext, session: AsyncSession):
    doc = message.document
    if not (doc.file_name.endswith(".xlsx") or doc.file_name.endswith(".xls")):
        await message.answer("❌ Fays formati noto'g'ri! Iltimos, faqat <b>.xlsx</b> kengaytmasidagi fayl yuboring.", parse_mode="HTML")
        return

    await message.answer("⏳ Excel fayl tahlil qilinmoqda va bazaga yuklanmoqda...")

    file_bytes = await message.bot.download(doc.file_id)
    file_content = file_bytes.read()

    # Build category map for matching
    categories = await get_user_categories(session, message.from_user.id)
    cat_map = {c.name.lower(): c.id for c in categories}

    valid_records, errors = parse_and_validate_excel(file_content, cat_map)

    if not valid_records and errors:
        err_msg = "❌ <b>Excel yuklashda xatoliklar yuz berdi:</b>\n\n" + "\n".join(errors[:10])
        await message.answer(err_msg, parse_mode="HTML")
        await state.clear()
        return

    added_count = 0
    for rec in valid_records:
        await add_expense(
            session=session,
            user_id=message.from_user.id,
            category_id=rec["category_id"],
            amount=rec["amount"],
            description=rec["description"],
            expense_date=rec["expense_date"],
            transaction_type=rec.get("transaction_type", "expense")
        )
        added_count += 1

    await state.clear()

    res_text = f"✅ <b>Muvaffaqiyatli import qilindi!</b>\n\n📥 <b>{added_count} ta</b> yangi xarajat ma'lumotlar bazasiga qo'shildi."
    if errors:
        res_text += f"\n\n⚠️ <b>Quyidagi {len(errors)} ta qatorda xatolik bo'lgani uchun o'tkazib yuborildi:</b>\n" + "\n".join(errors[:5])

    await message.answer(res_text, parse_mode="HTML")
