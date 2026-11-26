from fastapi import APIRouter

from app.modules.accounts.router import router as accounts_router
from app.modules.applications.review_router import router as application_review_router
from app.modules.applications.router import router as applications_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.candidates.router import router as candidates_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.recruitment.public_router import router as public_jobs_router
from app.modules.recruitment.router import router as recruitment_router
from app.modules.responses.router import router as responses_router

# Các router con dùng chung tiền tố /api/v1 do app gắn; quyền tuyển dụng được
# kiểm tra tại từng endpoint bằng HrPrincipal, không dựa vào menu frontend.
api_router = APIRouter()
for router in (
    auth_router,
    accounts_router,
    audit_router,
    candidates_router,
    applications_router,
    application_review_router,
    recommendations_router,
    recruitment_router,
    public_jobs_router,
    responses_router,
):
    api_router.include_router(router)
