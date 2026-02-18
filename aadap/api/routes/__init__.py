"""
AADAP — API Routes Package
=============================
Aggregates all Phase 7 route modules under ``/api/v1``.
"""

from aadap.api.routes.tasks import router as tasks_router
from aadap.api.routes.approvals import router as approvals_router
from aadap.api.routes.artifacts import router as artifacts_router
from aadap.api.routes.marketplace import router as marketplace_router
from aadap.api.routes.execution import router as execution_router

__all__ = [
    "tasks_router",
    "approvals_router",
    "artifacts_router",
    "marketplace_router",
    "execution_router",
]
