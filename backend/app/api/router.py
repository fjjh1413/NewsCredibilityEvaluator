from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_detections import router as admin_detections_router
from app.api.v1.admin_knowledge import router as admin_knowledge_router
from app.api.v1.auth import router as auth_router
from app.api.v1.detect import router as detect_router
from app.api.v1.health import router as health_router
from app.api.v1.rag import router as rag_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(admin_detections_router)
api_router.include_router(admin_knowledge_router)
api_router.include_router(detect_router)
api_router.include_router(rag_router)
api_router.include_router(health_router)
