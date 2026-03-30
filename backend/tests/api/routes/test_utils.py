from httpx import AsyncClient

from app.core.config import settings


async def test_health_check(client: AsyncClient) -> None:
    r = await client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert r.status_code == 200
    assert r.json() is True
