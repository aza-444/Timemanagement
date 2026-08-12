from aiogram import Router
from handlers.start import start_router
from handlers.expense_crud import expense_router
from handlers.analytics import analytics_router
from handlers.excel_handler import excel_router
from handlers.settings import settings_router
from handlers.admin import admin_router
from handlers.wallet import wallet_router

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(wallet_router)
main_router.include_router(analytics_router)
main_router.include_router(excel_router)
main_router.include_router(settings_router)
main_router.include_router(admin_router)
main_router.include_router(expense_router)

