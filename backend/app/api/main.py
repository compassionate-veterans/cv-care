from fastapi import APIRouter

from app.api.routes import attendance, auth, consent, patients, users, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(consent.router)
api_router.include_router(attendance.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)

if settings.ENVIRONMENT == "local":
    from app.api.routes import private

    api_router.include_router(private.router)
