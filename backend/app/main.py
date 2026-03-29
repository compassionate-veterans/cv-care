import contextlib
from collections.abc import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app import fhir
from app.api.main import api_router
from app.core import client, config


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if config.settings.SENTRY_DSN and config.settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(config.settings.SENTRY_DSN), enable_tracing=True)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.fhir = fhir.Client(client.create_http_client(), base_url=config.settings.FHIR_BASE_URL)
    yield
    await app.state.fhir.close()


app = FastAPI(
    title=config.settings.PROJECT_NAME,
    openapi_url=f"{config.settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if config.settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=config.settings.API_V1_STR)
