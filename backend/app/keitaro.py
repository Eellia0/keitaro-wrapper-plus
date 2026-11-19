import httpx
from fastapi import HTTPException

from app.config import settings


async def request_resource(method: str, resource: str, payload=None):
    if not settings.keitaro_base_url or not settings.keitaro_api_key:
        raise HTTPException(503, "Заполните настройки Keitaro в backend/.env")
    base_url = settings.keitaro_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method,
                f"{base_url}/admin_api/v1/{resource}",
                headers={"Api-Key": settings.keitaro_api_key},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        message = "Keitaro отклонил запрос"
        if status in (401, 403):
            message = "Проверьте API-ключ и права доступа к Keitaro"
        raise HTTPException(502, message) from error
    except (httpx.RequestError, ValueError) as error:
        raise HTTPException(502, "Не удалось получить данные Keitaro") from error


async def get_resource(resource: str):
    return await request_resource("GET", resource)
