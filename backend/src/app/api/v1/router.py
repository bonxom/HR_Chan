from fastapi import APIRouter

from app.modules.applications.router import router as applications_router
from app.modules.auth.router import router as auth_router
from app.modules.candidates.router import router as candidates_router
from app.modules.recommendations.router import router as recommendations_router

api_router = APIRouter()
for router in (
    auth_router,
    candidates_router,
    applications_router,
    recommendations_router,
):
    api_router.include_router(router)
