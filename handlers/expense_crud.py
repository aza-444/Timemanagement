from datetime import datetime, date, timedelta
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_helper import (
    get_user_categories,
    create_category,
    add_expense,
    get_expenses,
    get_paginated_expenses,
    get_user_balance_summary,
    delete_expense,
    get_expense_by_id,
    update_expense
)
from database.models import Category, Expense
from services.amount_parser import parse_amount, parse_quick_add, parse_quick_add_with_type, parse_flexible_date, AMOUNT_HINT, INCOME_HINT

expense_router = Router()

# Menu buttons (skip quick-add for these)
MENU_BUTTONS = {
    "➕ Xarajat Qo'shish", "💰 Kirim Qo'shish",
    "📋 Xarajatlar (Ro'yxat & CRUD)",
    "📊 Grafik Tahlil", "📁 Excel (Eksport & Import)",
    "⚙️ Sozlamalar (Eslatma)", "👑 Admin Panel",
    "💳 Mening Balansim", "/start",
}


class AddExpenseState(StatesGroup):
    select_category = State()
    enter_amount = State()
    enter_description = State()
    select_date = State()
    new_category_name = State()
    confirm_expense = State()
    # Edit sub-states (from confirmation)
    edit_amount = State()
    edit_description = State()
    edit_date = State()
    edit_category = State()


class EditExpenseState(StatesGroup):
    """States for editing an existing saved expense from the list."""
    edit_amount = State()
    edit_description = State()
    edit_date = State()
    edit_category = State()
    new_category_name = State()


# ── Keyboards ────────────────────────────────────────────────────────────────

def build_category_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=cat.name, callback_data=f"cat_select_{cat.id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="➕ Yangi Kategoriya Qo'shish", callback_data="add_new_category")])
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_expense")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, saqlansin!", callback_data="confirm_save_expense"),
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="edit_expense_menu"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_expense")],
    ])


def edit_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Kategoriyani o'zgartirish", callback_data="edit_field_category")],
        [InlineKeyboardButton(text="💰 Summani o'zgartirish",      callback_data="edit_field_amount")],
        [InlineKeyboardButton(text="📝 Izohni o'zgartirish",       callback_data="edit_field_description")],
        [InlineKeyboardButton(text="📅 Sanani o'zgartirish",       callback_data="edit_field_date")],
        [InlineKeyboardButton(text="↩️ Ortga (Tasdiqlash)",        callback_data="back_to_confirm")],
    ])


def fmt(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


# ── Confirmation display ──────────────────────────────────────────────────────

async def show_confirmation(message: Message, state: FSMContext, edit_msg=None):
    data = await state.get_data()
    cat = data.get("category_name", "Noma'lum")
    amount = data.get("amount", 0)
    desc = data.get("description") or ""
    exp_date = data.get("exp_date", str(date.today()))
    tx_type = data.get("transaction_type", "expense")
    desc_line = f"\n📝 <b>Izoh:</b> {desc}" if desc else ""
    type_label = "💰 <b>Kirim</b>" if tx_type == "income" else "🔴 <b>Xarajat</b>"

    text = (
        f"📋 <b>Tasdiqlang:</b> {type_label}\n\n"
        f"📂 <b>Kategoriya:</b> {cat}\n"
        f"💰 <b>Summa:</b> {fmt(amount)} so'm\n"
        f"📅 <b>Sana:</b> {exp_date}"
        f"{desc_line}\n\n"
        f"<i>✅ Ha, saqlansin — yoki ✏️ Tahrirlash bosing.</i>"
    )
    await state.set_state(AddExpenseState.confirm_expense)
    if edit_msg:
        try:
            await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_keyboard())
            return
        except Exception:
            pass
    await message.answer(text, parse_mode="HTML", reply_markup=confirm_keyboard())


# ── Start add expense ─────────────────────────────────────────────────────────

@expense_router.message(F.text == "➕ Xarajat Qo'shish", StateFilter("*"))
@expense_router.callback_query(F.data == "add_expense_start")
async def start_add_expense(event: Message | CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await state.update_data(transaction_type="expense")
    user_id = event.from_user.id
    categories = await get_user_categories(session, user_id)
    kb = build_category_keyboard(categories)
    text = "📂 <b>Xarajat kategoriyasini tanlang:</b>"
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(AddExpenseState.select_category)


# ── Quick-add: any text outside FSM ──────────────────────────────────────────

@expense_router.message(
    StateFilter(default_state),
    F.text,
    ~F.text.in_(MENU_BUTTONS),
    ~F.text.startswith("/")
)
async def quick_add_handler(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text.strip()
    result = parse_quick_add_with_type(text)
    if result is None:
        return  # Not a quick-add — ignore silently

    amount, description, tx_type, parsed_date = result
    await state.clear()

    # Default: Boshqa kategoriya
    categories = await get_user_categories(session, message.from_user.id)
    default_cat = next((c for c in categories if "boshqa" in c.name.lower()), categories[0] if categories else None)
    cat_id = default_cat.id if default_cat else None
    cat_name = default_cat.name if default_cat else "Noma'lum"

    exp_date_str = str(parsed_date) if parsed_date else str(date.today())

    await state.update_data(
        amount=amount,
        description=description or None,
        exp_date=exp_date_str,
        category_id=cat_id,
        category_name=cat_name,
        transaction_type=tx_type,
    )
    await show_confirmation(message, state)


# ── Category selection ────────────────────────────────────────────────────────

@expense_router.callback_query(F.data == "add_new_category", AddExpenseState.select_category)
@expense_router.callback_query(F.data == "add_new_category", AddExpenseState.edit_category)
async def prompt_new_category(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(
        "✍️ <b>Yangi kategoriya nomini kiriting:</b>\n<i>(Masalan: 🎮 O'yinlar)</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddExpenseState.new_category_name)


@expense_router.message(AddExpenseState.new_category_name)
async def process_new_category(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return

    cat_name = text_val
    if not cat_name:
        await message.answer("❌ Kategoriya nomi bo'sh bo'lishi mumkin emas.")
        return
    cat = await create_category(session, message.from_user.id, cat_name)
    await state.update_data(category_id=cat.id, category_name=cat.name)

    data = await state.get_data()
    if data.get("amount"):  # Coming from edit
        await show_confirmation(message, state)
    else:
        await message.answer(
            f"✅ <b>'{cat.name}'</b> yaratildi!\n\n💰 <b>Summani kiriting:</b>\n{AMOUNT_HINT}",
            parse_mode="HTML"
        )
        await state.set_state(AddExpenseState.enter_amount)


@expense_router.callback_query(F.data.startswith("cat_select_"), AddExpenseState.select_category)
@expense_router.callback_query(F.data.startswith("cat_select_"), AddExpenseState.edit_category)
async def category_selected(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    cat_id = int(call.data.split("_")[2])
    categories = await get_user_categories(session, call.from_user.id)
    selected_cat = next((c for c in categories if c.id == cat_id), None)
    cat_name = selected_cat.name if selected_cat else "Kategoriya"
    await state.update_data(category_id=cat_id, category_name=cat_name)
    await call.answer()

    data = await state.get_data()
    if data.get("amount"):  # Came from edit
        await show_confirmation(call.message, state)
    else:
        await call.message.answer(
            f"📂 Tanlandi: <b>{cat_name}</b>\n\n💰 <b>Summani kiriting:</b>\n{AMOUNT_HINT}",
            parse_mode="HTML"
        )
        await state.set_state(AddExpenseState.enter_amount)


# ── Amount ────────────────────────────────────────────────────────────────────

@expense_router.message(AddExpenseState.enter_amount)
@expense_router.message(AddExpenseState.edit_amount)
async def process_amount(message: Message, state: FSMContext):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return

    amount = parse_amount(text_val)
    if amount is None:
        await message.answer(
            f"❌ Noto'g'ri summa. Formatdan foydalaning:\n{AMOUNT_HINT}",
            parse_mode="HTML"
        )
        return
    await state.update_data(amount=amount)

    data = await state.get_data()
    if await state.get_state() == AddExpenseState.edit_amount:
        await show_confirmation(message, state)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Izohsiz o'tish", callback_data="skip_description")]
    ])
    await message.answer(
        f"💵 Summa: <b>{fmt(amount)} so'm</b>\n\n✍️ <b>Izoh kiriting (ixtiyoriy):</b>",
        parse_mode="HTML", reply_markup=kb
    )
    await state.set_state(AddExpenseState.enter_description)


# ── Description ───────────────────────────────────────────────────────────────

@expense_router.callback_query(F.data == "skip_description", AddExpenseState.enter_description)
async def skip_description(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(description=None)
    await ask_date(call.message, state)


@expense_router.message(AddExpenseState.enter_description)
async def process_description(message: Message, state: FSMContext):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return

    await state.update_data(description=text_val)
    await ask_date(message, state)


@expense_router.message(AddExpenseState.edit_description)
async def process_edit_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await show_confirmation(message, state)


# ── Date ──────────────────────────────────────────────────────────────────────

async def ask_date(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Bugun", callback_data="date_today"),
            InlineKeyboardButton(text="📆 Kecha", callback_data="date_yesterday"),
        ],
        [InlineKeyboardButton(text="🗓 Boshqa sana (YYYY-MM-DD)", callback_data="date_custom")],
    ])
    await message.answer("📅 <b>Xarajat sanasini tanlang:</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(AddExpenseState.select_date)


@expense_router.callback_query(F.data.startswith("date_"), AddExpenseState.select_date)
@expense_router.callback_query(F.data.startswith("date_"), AddExpenseState.edit_date)
async def process_date_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    action = call.data.split("_")[1]
    if action == "today":
        exp_date = date.today()
    elif action == "yesterday":
        exp_date = date.today() - timedelta(days=1)
    else:
        await call.answer()
        await call.message.answer("✍️ Sanani YYYY-MM-DD shaklida kiriting:")
        return
    await call.answer()
    await state.update_data(exp_date=str(exp_date))
    await show_confirmation(call.message, state)


@expense_router.message(AddExpenseState.select_date)
@expense_router.message(AddExpenseState.edit_date)
async def process_custom_date(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return
    exp_date = parse_flexible_date(text_val)
    if exp_date is None:
        await message.answer(
            "❌ Sanani tushunmadim. Quyidagi formatlarda yozing:\n"
            "<code>10-avgust</code>, <code>10.08</code>, <code>10.08.2026</code>, "
            "<code>2026-08-10</code>, <code>kecha</code>, <code>bugun</code>",
            parse_mode="HTML"
        )
        return
    await state.update_data(exp_date=str(exp_date))
    await show_confirmation(message, state)


# ── Confirmation actions ──────────────────────────────────────────────────────

@expense_router.callback_query(F.data == "confirm_save_expense", AddExpenseState.confirm_expense)
async def confirm_and_save(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    cat_id = data.get("category_id")
    cat_name = data.get("category_name", "Noma'lum")
    amount = data.get("amount")
    description = data.get("description")
    exp_date = datetime.strptime(data["exp_date"], "%Y-%m-%d").date()
    tx_type = data.get("transaction_type", "expense")

    expense = await add_expense(
        session=session,
        user_id=call.from_user.id,
        category_id=cat_id,
        amount=amount,
        description=description,
        expense_date=exp_date,
        transaction_type=tx_type
    )
    await state.clear()

    type_label = "💰 Kirim" if tx_type == "income" else "🔴 Xarajat"
    desc_line = f"\n📝 <b>Izoh:</b> {description}" if description else ""
    await call.message.edit_text(
        f"✅ <b>{type_label} saqlandi!</b>\n\n"
        f"📌 <b>ID:</b> #{expense.id}\n"
        f"📂 <b>Kategoriya:</b> {cat_name}\n"
        f"💰 <b>Summa:</b> {fmt(amount)} so'm\n"
        f"📅 <b>Sana:</b> {exp_date.strftime('%Y-%m-%d')}"
        f"{desc_line}",
        parse_mode="HTML"
    )


@expense_router.callback_query(F.data == "edit_expense_menu")
async def show_edit_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text(
        "✏️ <b>Qaysi bo'limni tahrirlaysiz?</b>",
        parse_mode="HTML",
        reply_markup=edit_menu_keyboard()
    )


@expense_router.callback_query(F.data == "back_to_confirm")
async def back_to_confirm(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_confirmation(call.message, state, edit_msg=call.message)


@expense_router.callback_query(F.data == "edit_field_category")
async def edit_category(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    categories = await get_user_categories(session, call.from_user.id)
    kb = build_category_keyboard(categories)
    await call.message.edit_text("📂 <b>Yangi kategoriyani tanlang:</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(AddExpenseState.edit_category)


@expense_router.callback_query(F.data == "edit_field_amount")
async def edit_amount(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(f"💰 <b>Yangi summani kiriting:</b>\n{AMOUNT_HINT}", parse_mode="HTML")
    await state.set_state(AddExpenseState.edit_amount)


@expense_router.callback_query(F.data == "edit_field_description")
async def edit_description_prompt(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("📝 <b>Yangi izohni kiriting:</b>", parse_mode="HTML")
    await state.set_state(AddExpenseState.edit_description)


@expense_router.callback_query(F.data == "edit_field_date")
async def edit_date_prompt(call: CallbackQuery, state: FSMContext):
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Bugun", callback_data="date_today"),
            InlineKeyboardButton(text="📆 Kecha", callback_data="date_yesterday"),
        ],
        [InlineKeyboardButton(text="🗓 Boshqa sana (YYYY-MM-DD)", callback_data="date_custom")],
    ])
    await call.message.answer("📅 <b>Yangi sanani tanlang:</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(AddExpenseState.edit_date)


@expense_router.callback_query(F.data == "cancel_expense")
async def cancel_expense_flow(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Bekor qilindi.")
    await call.message.edit_text("❌ Xarajat kiritish bekor qilindi.")


@expense_router.message(F.text == "💰 Kirim Qo'shish", StateFilter("*"))
async def start_add_income(event: Message | CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await state.update_data(transaction_type="income")
    user_id = event.from_user.id
    categories = await get_user_categories(session, user_id)
    kb = build_category_keyboard(categories)
    text = "💰 <b>Kirim kategoriyasini tanlang:</b>"
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(AddExpenseState.select_category)


# ── LIST & DELETE ─────────────────────────────────────────────────────────────

@expense_router.message(F.text == "📋 Xarajatlar (Ro'yxat & CRUD)", StateFilter("*"))
async def show_expenses_menu(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Xarajatlar", callback_data="view_exp_all_1_expense"),
            InlineKeyboardButton(text="🟢 Kirimlar",   callback_data="view_exp_all_1_income"),
        ],
        [
            InlineKeyboardButton(text="📅 Bugungi Xarajat", callback_data="view_exp_today_1_expense"),
            InlineKeyboardButton(text="📅 Shu Oylik Xarajat", callback_data="view_exp_month_1_expense"),
        ],
        [
            InlineKeyboardButton(text="📋 Barcha Operatsiyalar", callback_data="view_exp_all_1_all")
        ]
    ])
    await message.answer("📋 <b>Qaysi operatsiyalarni ko'rmoqchisiz?</b>", parse_mode="HTML", reply_markup=kb)


@expense_router.callback_query(F.data.startswith("view_exp_"))
async def filter_expenses_list(call: CallbackQuery, session: AsyncSession):
    parts = call.data.split("_")
    period = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 1
    tx_type = parts[4] if len(parts) > 4 else "expense"
    
    user_id = call.from_user.id
    today = date.today()
    start_d = end_d = None

    type_label = "Kirimlar" if tx_type == "income" else ("Operatsiyalar" if tx_type == "all" else "Xarajatlar")

    if period == "today":
        start_d = end_d = today
        title = f"Bugungi {type_label}"
    elif period == "week":
        start_d = today - timedelta(days=today.weekday())
        end_d = today
        title = f"Shu Haftalik {type_label}"
    elif period == "month":
        start_d = today.replace(day=1)
        end_d = today
        title = f"Shu Oylik {type_label}"
    else:
        title = f"Barcha {type_label}"

    filter_tx = None if tx_type == "all" else tx_type
    ITEMS_PER_PAGE = 5
    page_items, total_items, total_sum = await get_paginated_expenses(
        session, user_id, start_d, end_d, page=page, limit=ITEMS_PER_PAGE, transaction_type=filter_tx
    )

    if total_items == 0:
        await call.answer()
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Ortga", callback_data="back_to_periods")
        ]])
        await call.message.edit_text(f"📭 <b>{title}</b> topilmadi.", parse_mode="HTML", reply_markup=kb)
        return

    await call.answer()
    
    # Calculate wallet info
    summary = await get_user_balance_summary(session, user_id)
    wallet = summary["wallet"]
    
    # Header
    text = f"📋 <b>{title} (Jami: {fmt(total_sum)} so'm):</b>\n"
    if wallet is not None:
        rem = summary["remaining"]
        text += f"💳 <b>Qolgan mablag': {fmt(rem)} so'm</b>\n"
    text += "\n"
    
    # Pagination total pages
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    for exp, cat in page_items:
        cat_name = cat.name if cat else "Noma'lum"
        desc_str = f" ({exp.description})" if exp.description else ""
        icon = "🟢" if exp.transaction_type == "income" else "🔴"
        text += f"{icon} <b>#{exp.id}</b> | {exp.expense_date} | {cat_name}: <b>{fmt(exp.amount)} so'm</b>{desc_str}\n"

    # Action Buttons — ALL expenses on the current page open edit/delete panel
    kb_buttons = []
    for e, cat in page_items:
        cat_label = cat.name if cat else "?"
        icon = "🟢" if e.transaction_type == "income" else "✏️"
        kb_buttons.append([InlineKeyboardButton(
            text=f"{icon} #{e.id} | {cat_label} | {fmt(e.amount)} so'm",
            callback_data=f"manage_exp_{e.id}"
        )])
        
    # Pagination Buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"view_exp_{period}_{page-1}_{tx_type}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"view_exp_{period}_{page+1}_{tx_type}"))
        
    if nav_row:
        kb_buttons.append(nav_row)
        
    # Back to periods button
    kb_buttons.append([InlineKeyboardButton(text="↩️ Ortga", callback_data="back_to_periods")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        # Ignore if Telegram message is identical
        pass


@expense_router.callback_query(F.data == "back_to_periods")
async def back_to_periods(call: CallbackQuery):
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Bugun",    callback_data="view_exp_today_1"),
            InlineKeyboardButton(text="Shu Hafta", callback_data="view_exp_week_1"),
        ],
        [
            InlineKeyboardButton(text="Shu Oy",   callback_data="view_exp_month_1"),
            InlineKeyboardButton(text="Barchasi", callback_data="view_exp_all_1"),
        ],
    ])
    await call.message.edit_text("📋 <b>Qaysi davr uchun xarajatlarni ko'rasiz?</b>", parse_mode="HTML", reply_markup=kb)



# ── Manage (Edit/Delete) existing expense ─────────────────────────────────────

def _manage_keyboard(exp_id: int, tx_type: str = "expense") -> InlineKeyboardMarkup:
    toggle_text = "🟢 Kirimga o'tkazish" if tx_type == "expense" else "🔴 Xarajatga o'tkazish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text,      callback_data=f"eedit_type_{exp_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Summa",      callback_data=f"eedit_amount_{exp_id}"),
            InlineKeyboardButton(text="📝 Izoh",       callback_data=f"eedit_desc_{exp_id}"),
        ],
        [
            InlineKeyboardButton(text="📂 Kategoriya", callback_data=f"eedit_cat_{exp_id}"),
            InlineKeyboardButton(text="📅 Sana",       callback_data=f"eedit_date_{exp_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 O'chirish",  callback_data=f"del_exp_{exp_id}"),
            InlineKeyboardButton(text="❌ Yopish",     callback_data="cancel_del"),
        ],
    ])


@expense_router.callback_query(F.data.startswith("manage_exp_"))
async def manage_expense(call: CallbackQuery, session: AsyncSession):
    exp_id = int(call.data.split("_")[2])
    item = await get_expense_by_id(session, call.from_user.id, exp_id)
    if not item:
        await call.answer("❌ Operatsiya topilmadi.", show_alert=True)
        return
    exp, cat = item
    await call.answer()
    tx_header = "🟢 Kirim" if exp.transaction_type == "income" else "🔴 Xarajat"
    text = (
        f"🔧 <b>Operatsiya #{exp.id} ({tx_header})</b>\n\n"
        f"📂 Kategoriya: {cat.name if cat else 'Noma\'lum'}\n"
        f"💰 Summa: <b>{fmt(exp.amount)} so'm</b>\n"
        f"📅 Sana: {exp.expense_date}\n"
        f"📝 Izoh: {exp.description or '—'}\n\n"
        f"Quyidagi tugmalar orqali o'zgartiring:"
    )
    await call.message.answer(text, parse_mode="HTML", reply_markup=_manage_keyboard(exp_id, exp.transaction_type))


@expense_router.callback_query(F.data.startswith("eedit_type_"))
async def toggle_exp_type(call: CallbackQuery, session: AsyncSession):
    exp_id = int(call.data.split("_")[2])
    item = await get_expense_by_id(session, call.from_user.id, exp_id)
    if not item:
        await call.answer("❌ Operatsiya topilmadi.", show_alert=True)
        return
    exp, cat = item
    new_type = "income" if exp.transaction_type == "expense" else "expense"
    await update_expense(session, call.from_user.id, exp_id, transaction_type=new_type)
    
    new_label = "🟢 Kirim" if new_type == "income" else "🔴 Xarajat"
    await call.answer(f"✅ Operatsiya turi {new_label}ga o'zgardi!", show_alert=True)
    
    # Refresh edit panel
    updated_item = await get_expense_by_id(session, call.from_user.id, exp_id)
    if updated_item:
        u_exp, u_cat = updated_item
        tx_header = "🟢 Kirim" if u_exp.transaction_type == "income" else "🔴 Xarajat"
        text = (
            f"🔧 <b>Operatsiya #{u_exp.id} ({tx_header})</b>\n\n"
            f"📂 Kategoriya: {u_cat.name if u_cat else 'Noma\'lum'}\n"
            f"💰 Summa: <b>{fmt(u_exp.amount)} so'm</b>\n"
            f"📅 Sana: {u_exp.expense_date}\n"
            f"📝 Izoh: {u_exp.description or '—'}\n\n"
            f"Quyidagi tugmalar orqali o'zgartiring:"
        )
        try:
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=_manage_keyboard(exp_id, u_exp.transaction_type))
        except Exception:
            pass


# ── Edit amount ──────────────────────────────────────────────────────────────

@expense_router.callback_query(F.data.startswith("eedit_amount_"))
async def edit_exp_amount_prompt(call: CallbackQuery, state: FSMContext):
    exp_id = int(call.data.split("_")[2])
    await state.set_state(EditExpenseState.edit_amount)
    await state.update_data(editing_exp_id=exp_id)
    await call.answer()
    await call.message.answer(
        f"💰 <b>#{exp_id} uchun yangi summani kiriting:</b>\n{AMOUNT_HINT}",
        parse_mode="HTML"
    )


@expense_router.message(EditExpenseState.edit_amount)
async def edit_exp_amount_save(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return
    amount = parse_amount(text_val)
    if amount is None:
        await message.answer(f"❌ Noto'g'ri summa.\n{AMOUNT_HINT}", parse_mode="HTML")
        return
    data = await state.get_data()
    exp_id = data["editing_exp_id"]
    await update_expense(session, message.from_user.id, exp_id, amount=amount)
    await state.clear()
    await message.answer(
        f"✅ <b>#{exp_id} summasi yangilandi: {fmt(amount)} so'm</b>",
        parse_mode="HTML"
    )


# ── Edit description ─────────────────────────────────────────────────────────

@expense_router.callback_query(F.data.startswith("eedit_desc_"))
async def edit_exp_desc_prompt(call: CallbackQuery, state: FSMContext):
    exp_id = int(call.data.split("_")[2])
    await state.set_state(EditExpenseState.edit_description)
    await state.update_data(editing_exp_id=exp_id)
    await call.answer()
    await call.message.answer(
        f"📝 <b>#{exp_id} uchun yangi izohni kiriting:</b>\n<i>(bo'sh qoldirish uchun — yuboring)</i>",
        parse_mode="HTML"
    )


@expense_router.message(EditExpenseState.edit_description)
async def edit_exp_desc_save(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return
    data = await state.get_data()
    exp_id = data["editing_exp_id"]
    desc = None if text_val == "—" else text_val
    await update_expense(session, message.from_user.id, exp_id, description=desc or "")
    await state.clear()
    await message.answer(f"✅ <b>#{exp_id} izohi yangilandi.</b>", parse_mode="HTML")


# ── Edit date ────────────────────────────────────────────────────────────────

@expense_router.callback_query(F.data.startswith("eedit_date_"))
async def edit_exp_date_prompt(call: CallbackQuery, state: FSMContext):
    exp_id = int(call.data.split("_")[2])
    await state.set_state(EditExpenseState.edit_date)
    await state.update_data(editing_exp_id=exp_id)
    await call.answer()
    today = date.today()
    await call.message.answer(
        f"📅 <b>#{exp_id} uchun yangi sanani kiriting:</b>\n"
        f"<i>Istalgan formatda yozing: <code>10-avgust</code>, <code>10.08</code>, "
        f"<code>10.08.2026</code>, <code>2026-08-10</code>, <code>kecha</code>, <code>bugun</code></i>",
        parse_mode="HTML"
    )


@expense_router.message(EditExpenseState.edit_date)
async def edit_exp_date_save(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return
    new_date = parse_flexible_date(text_val)
    if new_date is None:
        await message.answer(
            "❌ Sanani tushunmadim. Quyidagi formatlarda yozing:\n"
            "<code>10-avgust</code>, <code>10.08</code>, <code>10.08.2026</code>, "
            "<code>2026-08-10</code>, <code>kecha</code>, <code>bugun</code>",
            parse_mode="HTML"
        )
        return
    data = await state.get_data()
    exp_id = data["editing_exp_id"]
    await update_expense(session, message.from_user.id, exp_id, expense_date=new_date)
    await state.clear()
    await message.answer(f"✅ <b>#{exp_id} sanasi yangilandi: {new_date}</b>", parse_mode="HTML")


# ── Edit category ─────────────────────────────────────────────────────────────

@expense_router.callback_query(F.data.startswith("eedit_cat_"))
async def edit_exp_cat_prompt(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    exp_id = int(call.data.split("_")[2])
    await state.set_state(EditExpenseState.edit_category)
    await state.update_data(editing_exp_id=exp_id)
    categories = await get_user_categories(session, call.from_user.id)
    kb = build_category_keyboard(categories)
    await call.answer()
    await call.message.answer(
        f"📂 <b>#{exp_id} uchun yangi kategoriyani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb
    )


@expense_router.callback_query(EditExpenseState.edit_category, F.data.startswith("cat_select_"))
async def edit_exp_cat_select(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    cat_id = int(call.data.split("_")[2])
    data = await state.get_data()
    exp_id = data["editing_exp_id"]
    await update_expense(session, call.from_user.id, exp_id, category_id=cat_id)
    await state.clear()
    await call.answer()
    await call.message.edit_text(f"✅ <b>#{exp_id} kategoriyasi yangilandi.</b>", parse_mode="HTML")


@expense_router.callback_query(EditExpenseState.edit_category, F.data == "add_new_category")
async def edit_exp_new_cat_prompt(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(EditExpenseState.new_category_name)
    await call.message.answer("✍️ <b>Yangi kategoriya nomini kiriting:</b>", parse_mode="HTML")


@expense_router.message(EditExpenseState.new_category_name)
async def edit_exp_new_cat_save(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip() if message.text else ""
    if text_val in MENU_BUTTONS or text_val.startswith("/"):
        await state.clear()
        return
    if not text_val:
        await message.answer("❌ Kategoriya nomi bo'sh bo'lishi mumkin emas.")
        return
    data = await state.get_data()
    exp_id = data["editing_exp_id"]
    cat = await create_category(session, message.from_user.id, text_val)
    await update_expense(session, message.from_user.id, exp_id, category_id=cat.id)
    await state.clear()
    await message.answer(
        f"✅ <b>#{exp_id} kategoriyasi '{cat.name}' ga yangilandi.</b>",
        parse_mode="HTML"
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@expense_router.callback_query(F.data.startswith("del_exp_"))
async def confirm_delete_expense(call: CallbackQuery, session: AsyncSession):
    exp_id = int(call.data.split("_")[2])
    item = await get_expense_by_id(session, call.from_user.id, exp_id)
    if not item:
        await call.answer("❌ Xarajat topilmadi.", show_alert=True)
        return
    exp, cat = item
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirilsin", callback_data=f"confirm_del_{exp_id}"),
        InlineKeyboardButton(text="❌ Bekor",           callback_data="cancel_del"),
    ]])
    await call.answer()
    await call.message.answer(
        f"⚠️ <b>O'chirilsinmi?</b>\n\n"
        f"📌 ID: #{exp.id} | 📂 {cat.name if cat else ''} | "
        f"💰 {fmt(exp.amount)} so'm | 📅 {exp.expense_date}",
        parse_mode="HTML", reply_markup=kb
    )


@expense_router.callback_query(F.data.startswith("confirm_del_"))
async def execute_delete(call: CallbackQuery, session: AsyncSession):
    exp_id = int(call.data.split("_")[2])
    ok = await delete_expense(session, call.from_user.id, exp_id)
    await call.answer()
    if ok:
        await call.message.edit_text(f"🗑 <b>#{exp_id} o'chirildi.</b>", parse_mode="HTML")
    else:
        await call.message.answer("❌ O'chirishda xatolik.")


@expense_router.callback_query(F.data == "cancel_del")
async def cancel_delete(call: CallbackQuery):
    await call.answer("Bekor qilindi.")
    await call.message.delete()


@expense_router.callback_query(F.data == "ignore")
async def ignore_callback(call: CallbackQuery):
    await call.answer()

