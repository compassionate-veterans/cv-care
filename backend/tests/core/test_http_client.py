import httpx

from app.core.client import HttpxClient, RetryingHttpxClient, _is_retryable_response, create_http_client


def test_create_client_default_is_httpx() -> None:
    assert isinstance(create_http_client(), HttpxClient)


def test_create_client_with_retry() -> None:
    assert isinstance(create_http_client(retry=True), RetryingHttpxClient)


def test_retryable_status_codes() -> None:
    for code in (408, 429, 500, 502, 503, 504):
        resp = httpx.Response(status_code=code)
        assert _is_retryable_response(resp), f"{code} should be retryable"

    for code in (200, 201, 400, 401, 403, 404, 422):
        resp = httpx.Response(status_code=code)
        assert not _is_retryable_response(resp), f"{code} should not be retryable"
