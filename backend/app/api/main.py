from fastapi import APIRouter

from app.api.routes import auth, users, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)

if settings.ENVIRONMENT == "local":
    from app.api.routes import private

    api_router.include_router(private.router)
