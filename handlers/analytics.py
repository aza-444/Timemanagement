from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_helper import get_expenses
from services.chart_service import generate_expense_charts

from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

analytics_router = Router()


@analytics_router.message(F.text == "📊 Grafik Tahlil", StateFilter("*"))
async def show_analytics_options(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Xarajatlar Tahlili", callback_data="chart_all_expense"),
            InlineKeyboardButton(text="🟢 Kirimlar Tahlili",   callback_data="chart_all_income")
        ],
        [
            InlineKeyboardButton(text="📅 Bugungi Xarajat", callback_data="chart_today_expense"),
            InlineKeyboardButton(text="🗓 Shu Oylik Xarajat", callback_data="chart_month_expense")
        ]
    ])

    await message.answer(
        "📊 <b>Grafik tahlil bo'limiga xush kelibsiz:</b>\n"
        "Qaysi operatsiyalar bo'yicha vizual grafik diagramma va statistika olmoqchisiz?",
        parse_mode="HTML",
        reply_markup=kb
    )


@analytics_router.callback_query(F.data.startswith("chart_"))
async def process_chart_analytics(call: CallbackQuery, session: AsyncSession):
    parts = call.data.split("_")
    period = parts[1]
    tx_type = parts[2] if len(parts) > 2 else "expense"
    user_id = call.from_user.id

    today = date.today()
    start_d = None
    end_d = None

    type_title = "Kirimlar" if tx_type == "income" else "Xarajatlar"

    if period == "today":
        start_d = today
        end_d = today
        title = f"Bugungi {type_title} Tahlili"
    elif period == "week":
        start_d = today - timedelta(days=today.weekday())
        end_d = today
        title = f"Shu Haftalik {type_title} Tahlili"
    elif period == "month":
        start_d = today.replace(day=1)
        end_d = today
        title = f"Shu Oylik {type_title} Tahlili"
    else:
        title = f"Barcha Davrlardagi {type_title} Tahlili"

    await call.answer("📊 Diagramma shakllantirilmoqda...", show_alert=False)

    expenses_data = await get_expenses(session, user_id, start_d, end_d, transaction_type=tx_type)

    if not expenses_data:
        await call.message.answer(
            f"📭 <b>{title}</b> bo'yicha ma'lumotlar topilmadi.",
            parse_mode="HTML"
        )
        return

    buf = generate_expense_charts(expenses_data, period_title=title)

    if not buf:
        await call.message.answer("❌ Diagramma yaratishda xatolik yuz berdi.")
        return

    photo_file = BufferedInputFile(buf.getvalue(), filename="chart.png")

    total_amount = sum(exp.amount for exp, _ in expenses_data)
    count = len(expenses_data)

    cat_totals = {}
    for exp, cat in expenses_data:
        cat_name = cat.name if cat else "Noma'lum"
        cat_totals[cat_name] = cat_totals.get(cat_name, 0.0) + exp.amount

    top_cat = max(cat_totals.items(), key=lambda x: x[1]) if cat_totals else ("Noma'lum", 0.0)

    type_label = "🟢 Jami Kirim:" if tx_type == "income" else "🔴 Jami Xarajat:"

    caption_text = (
        f"📊 <b>{title}</b>\n\n"
        f"💰 <b>{type_label}</b> {total_amount:,.0f} so'm\n"
        f"🔢 <b>Tranzaksiyalar soni:</b> {count} ta\n"
        f"🔝 <b>Eng ko'p ulush:</b> {top_cat[0]} ({top_cat[1]:,.0f} so'm)\n\n"
        f"<i>Barcha ma'lumotlar sizning Telegram ID'ingizga tegishli.</i>"
    )

    await call.message.answer_photo(
        photo=photo_file,
        caption=caption_text,
        parse_mode="HTML"
    )
