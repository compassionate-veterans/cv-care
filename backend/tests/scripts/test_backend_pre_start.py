from app.backend_pre_start import init


async def test_init_successful_connection() -> None:
    await init()
