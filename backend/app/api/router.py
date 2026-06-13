from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_detections import router as admin_detections_router
from app.api.v1.admin_high_risk import router as admin_high_risk_router
from app.api.v1.admin_knowledge import router as admin_knowledge_router
from app.api.v1.admin_logs import router as admin_logs_router
from app.api.v1.admin_prompts import router as admin_prompts_router
from app.api.v1.admin_reports import router as admin_reports_router
from app.api.v1.admin_statistics import router as admin_statistics_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.detect import router as detect_router
from app.api.v1.health import router as health_router
from app.api.v1.high_risk import router as high_risk_router
from app.api.v1.rag import router as rag_router
from app.api.v1.report import router as report_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(admin_detections_router)
api_router.include_router(admin_high_risk_router)
api_router.include_router(admin_knowledge_router)
api_router.include_router(admin_logs_router)
api_router.include_router(admin_prompts_router)
api_router.include_router(admin_reports_router)
api_router.include_router(admin_statistics_router)
api_router.include_router(admin_users_router)
api_router.include_router(detect_router)
api_router.include_router(high_risk_router)
api_router.include_router(rag_router)
api_router.include_router(report_router)
api_router.include_router(health_router)
