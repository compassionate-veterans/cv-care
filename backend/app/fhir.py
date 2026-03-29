from fhir.resources.R4B.resource import Resource

from app.core.client import AsyncHTTPClient

FHIR_HEADERS = {"Content-Type": "application/fhir+json"}


class Client:
    def __init__(self, http: AsyncHTTPClient, base_url: str) -> None:
        self._http = http
        self._base_url = base_url

    async def close(self) -> None:
        await self._http.close()

    async def read[R: Resource](self, resource_type: type[R], resource_id: str) -> R:
        r = await self._http.get(f"{self._base_url}/{resource_type.__resource_type__}/{resource_id}")
        r.raise_for_status()
        return resource_type.model_validate(r.json())

    async def create[R: Resource](self, resource: R) -> R:
        r = await self._http.post(
            f"{self._base_url}/{resource.__class__.__resource_type__}",
            content=resource.model_dump_json(exclude_unset=True),
            headers=FHIR_HEADERS,
        )
        r.raise_for_status()
        return resource.__class__.model_validate(r.json())

    async def update[R: Resource](self, resource: R) -> R:
        r = await self._http.put(
            f"{self._base_url}/{resource.__class__.__resource_type__}/{resource.id}",
            content=resource.model_dump_json(exclude_unset=True),
            headers=FHIR_HEADERS,
        )
        r.raise_for_status()
        return resource.__class__.model_validate(r.json())

    async def search[R: Resource](self, resource_type: type[R], params: dict | None = None) -> list[R]:
        r = await self._http.get(
            f"{self._base_url}/{resource_type.__resource_type__}",
            params=params,
        )
        r.raise_for_status()
        bundle = r.json()
        if not bundle.get("entry"):
            return []
        return [resource_type.model_validate(e["resource"]) for e in bundle["entry"]]
