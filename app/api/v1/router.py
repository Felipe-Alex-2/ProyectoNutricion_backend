from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.roles import router as roles_router
from app.api.v1.organization_users import router as org_users_router
from app.api.v1.patient_links import router as patient_links_router
from app.api.v1.activity_logs import router as activity_logs_router
from app.api.v1.recipes import router as recipes_router
from app.api.v1.clinical import router as clinical_router

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(roles_router)
api_v1_router.include_router(org_users_router)
api_v1_router.include_router(patient_links_router)
api_v1_router.include_router(activity_logs_router)
api_v1_router.include_router(recipes_router)
api_v1_router.include_router(clinical_router)

