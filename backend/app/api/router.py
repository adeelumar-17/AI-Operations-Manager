'''
What the file does?
This module aggregates all domain API routers into a single master API router with
the /api/v1 prefix, and also registers the /internal router for EventBridge triggers.

Classes:
    None (Router aggregation module)

Methods:
    None (Module mounts chat, approvals, customers, products, quotes, orders,
    invoices, tasks, runs, and internal sub-routers)
'''

from fastapi import APIRouter
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.approvals import router as approvals_router
from backend.app.api.routes.customers import router as customers_router
from backend.app.api.routes.products import router as products_router
from backend.app.api.routes.quotes import router as quotes_router
from backend.app.api.routes.orders import router as orders_router
from backend.app.api.routes.invoices import router as invoices_router
from backend.app.api.routes.tasks import router as tasks_router
from backend.app.api.routes.runs import router as runs_router
from backend.app.api.routes.internal import router as internal_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(chat_router)
api_router.include_router(approvals_router)
api_router.include_router(customers_router)
api_router.include_router(products_router)
api_router.include_router(quotes_router)
api_router.include_router(orders_router)
api_router.include_router(invoices_router)
api_router.include_router(tasks_router)
api_router.include_router(runs_router)

# Internal router mounted at root (not under /api/v1) — called by EventBridge
api_router.include_router(internal_router)
