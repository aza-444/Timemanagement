from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, delete, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Category, Expense
from config import settings

DEFAULT_CATEGORIES = [
    "🍔 Oziq-ovqat",
    "🚗 Transport",
    "🏠 Kommunal / Uy",
    "🎬 Ko'ngilochar",
    "💊 Sog'liqni saqlash",
    "👕 Kiyim-kechak",
    "📚 Ta'lim",
    "💡 Boshqa"
]


async def seed_default_categories(session: AsyncSession):
    stmt = select(Category).where(Category.is_default == True)
    res = await session.execute(stmt)
    existing = res.scalars().all()
    existing_names = {c.name for c in existing}

    for cat_name in DEFAULT_CATEGORIES:
        if cat_name not in existing_names:
            category = Category(name=cat_name, is_default=True, user_id=None)
            session.add(category)
    await session.commit()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None
) -> User:
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    role = "ADMIN" if settings.is_admin(telegram_id) else "USER"

    if not user:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            role=role,
            reminder_time=settings.DEFAULT_REMINDER_TIME,
            is_reminder_active=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Update user info if changed
        updated = False
        if user.full_name != full_name:
            user.full_name = full_name
            updated = True
        if user.username != username:
            user.username = username
            updated = True
        if settings.is_admin(telegram_id) and user.role != "ADMIN":
            user.role = "ADMIN"
            updated = True
        if updated:
            await session.commit()

    return user


async def get_user_categories(session: AsyncSession, user_id: int) -> List[Category]:
    stmt = select(Category).where(
        or_(Category.is_default == True, Category.user_id == user_id)
    ).order_by(Category.is_default.desc(), Category.id.asc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def create_category(session: AsyncSession, user_id: int, name: str) -> Category:
    category = Category(user_id=user_id, name=name, is_default=False)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def add_expense(
    session: AsyncSession,
    user_id: int,
    category_id: int,
    amount: float,
    description: Optional[str],
    expense_date: date,
    transaction_type: str = "expense"
) -> Expense:
    expense = Expense(
        user_id=user_id,
        category_id=category_id,
        amount=amount,
        description=description,
        expense_date=expense_date,
        transaction_type=transaction_type
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def get_expenses(
    session: AsyncSession,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    transaction_type: Optional[str] = None  # None = all, 'expense' or 'income'
) -> List[Tuple[Expense, Optional[Category]]]:
    stmt = select(Expense, Category).outerjoin(Category, Expense.category_id == Category.id).where(
        Expense.user_id == user_id
    )
    if transaction_type:
        stmt = stmt.where(Expense.transaction_type == transaction_type)
    if start_date:
        stmt = stmt.where(Expense.expense_date >= start_date)
    if end_date:
        stmt = stmt.where(Expense.expense_date <= end_date)

    stmt = stmt.order_by(Expense.expense_date.desc(), Expense.id.desc())
    res = await session.execute(stmt)
    return list(res.all())


async def update_expense(
    session: AsyncSession,
    user_id: int,
    expense_id: int,
    amount: Optional[float] = None,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    expense_date: Optional[date] = None,
    transaction_type: Optional[str] = None
) -> bool:
    values = {}
    if amount is not None:
        values["amount"] = amount
    if category_id is not None:
        values["category_id"] = category_id
    if description is not None:
        values["description"] = description
    if expense_date is not None:
        values["expense_date"] = expense_date
    if transaction_type is not None:
        values["transaction_type"] = transaction_type

    if not values:
        return False

    stmt = update(Expense).where(Expense.id == expense_id, Expense.user_id == user_id).values(**values)
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount > 0


async def delete_expense(session: AsyncSession, user_id: int, expense_id: int) -> bool:
    stmt = delete(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount > 0


async def get_expense_by_id(session: AsyncSession, user_id: int, expense_id: int) -> Optional[Tuple[Expense, Optional[Category]]]:
    stmt = select(Expense, Category).outerjoin(Category, Expense.category_id == Category.id).where(
        Expense.id == expense_id,
        Expense.user_id == user_id
    )
    res = await session.execute(stmt)
    return res.first()


async def update_user_reminder(session: AsyncSession, user_id: int, reminder_time: str, is_active: bool) -> bool:
    stmt = update(User).where(User.telegram_id == user_id).values(
        reminder_time=reminder_time,
        is_reminder_active=is_active
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount > 0


async def get_active_reminder_users(session: AsyncSession) -> List[User]:
    stmt = select(User).where(User.is_reminder_active == True)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_admin_stats(session: AsyncSession) -> Dict[str, Any]:
    user_count_stmt = select(func.count(User.telegram_id))
    expense_count_stmt = select(func.count(Expense.id))
    total_amount_stmt = select(func.coalesce(func.sum(Expense.amount), 0.0))

    user_count = (await session.execute(user_count_stmt)).scalar_one()
    expense_count = (await session.execute(expense_count_stmt)).scalar_one()
    total_amount = (await session.execute(total_amount_stmt)).scalar_one()

    return {
        "user_count": user_count,
        "expense_count": expense_count,
        "total_amount": total_amount
    }


async def get_paginated_expenses(
    session: AsyncSession,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    limit: int = 10,
    transaction_type: Optional[str] = "expense"  # 'expense', 'income', or None for all
) -> Tuple[List[Tuple[Expense, Optional[Category]]], int, float]:
    """
    Fast SQL-level pagination and aggregate total calculation.
    Returns (items, total_count, total_sum).
    """
    base_where = [Expense.user_id == user_id]
    if transaction_type:
        base_where.append(Expense.transaction_type == transaction_type)
    if start_date:
        base_where.append(Expense.expense_date >= start_date)
    if end_date:
        base_where.append(Expense.expense_date <= end_date)

    # 1. Total count & sum aggregate query
    agg_stmt = select(
        func.count(Expense.id),
        func.coalesce(func.sum(Expense.amount), 0.0)
    ).where(*base_where)
    agg_res = await session.execute(agg_stmt)
    total_count, total_sum = agg_res.one()

    if total_count == 0:
        return [], 0, 0.0

    # 2. Paginated items query
    offset = (max(1, page) - 1) * limit
    stmt = (
        select(Expense, Category)
        .outerjoin(Category, Expense.category_id == Category.id)
        .where(*base_where)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    items = list(res.all())
    return items, int(total_count), float(total_sum)


async def update_wallet_balance(session: AsyncSession, user_id: int, balance: float) -> bool:
    stmt = update(User).where(User.telegram_id == user_id).values(wallet_balance=balance)
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount > 0


async def get_user_balance_summary(session: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Returns wallet balance, total income, total expenses, and net remaining.
    Formula: remaining = wallet_balance (if set) + total_income - total_expenses
    """
    user_stmt = select(User.wallet_balance).where(User.telegram_id == user_id)
    wallet = (await session.execute(user_stmt)).scalar_one_or_none()

    expense_stmt = select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
        Expense.user_id == user_id,
        Expense.transaction_type == "expense"
    )
    total_spent = float((await session.execute(expense_stmt)).scalar_one())

    income_stmt = select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
        Expense.user_id == user_id,
        Expense.transaction_type == "income"
    )
    total_income = float((await session.execute(income_stmt)).scalar_one())

    base = (wallet or 0.0) + total_income - total_spent
    remaining = base if (wallet is not None or total_income > 0) else None

    return {
        "wallet": wallet,
        "total_income": total_income,
        "total_spent": total_spent,
        "remaining": remaining,
    }

