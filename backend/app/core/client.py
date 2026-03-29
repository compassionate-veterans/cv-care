import abc
from collections.abc import Callable, Coroutine
from typing import Any

import httpx
import tenacity


class AsyncHTTPClient(abc.ABC):
    @abc.abstractmethod
    async def get(self, url: str, **kwargs: Any) -> httpx.Response: ...

    @abc.abstractmethod
    async def post(self, url: str, **kwargs: Any) -> httpx.Response: ...

    @abc.abstractmethod
    async def put(self, url: str, **kwargs: Any) -> httpx.Response: ...

    @abc.abstractmethod
    async def delete(self, url: str, **kwargs: Any) -> httpx.Response: ...

    @abc.abstractmethod
    async def close(self) -> None: ...


class HttpxClient(AsyncHTTPClient):
    def __init__(self, **client_kwargs: Any) -> None:
        self._client = httpx.AsyncClient(**client_kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.put(url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.delete(url, **kwargs)

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()


def _is_retryable_response(response: httpx.Response) -> bool:
    return response.status_code in (408, 429, 500, 502, 503, 504)


class RetryingHttpxClient(HttpxClient):
    def __init__(self, max_attempts: int = 3, **client_kwargs: Any) -> None:
        super().__init__(**client_kwargs)
        self._max_attempts = max_attempts

    def _with_retry(
        self,
        fn: Callable[..., Coroutine[Any, Any, httpx.Response]],
    ) -> Callable[..., Coroutine[Any, Any, httpx.Response]]:
        return tenacity.retry(
            retry=(
                tenacity.retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException))
                | tenacity.retry_if_result(_is_retryable_response)
            ),
            stop=tenacity.stop_after_attempt(self._max_attempts),
            wait=tenacity.wait_exponential(multiplier=0.5, min=0.5, max=10),
            reraise=True,
        )(fn)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._with_retry(super().get)(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._with_retry(super().post)(url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._with_retry(super().put)(url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._with_retry(super().delete)(url, **kwargs)


def create_http_client(
    retry: bool = False,
    max_attempts: int = 3,
    **client_kwargs: Any,
) -> AsyncHTTPClient:
    if retry:
        return RetryingHttpxClient(max_attempts=max_attempts, **client_kwargs)
    return HttpxClient(**client_kwargs)
