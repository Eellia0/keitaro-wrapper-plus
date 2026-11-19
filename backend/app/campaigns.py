from uuid import UUID, uuid4
import asyncio
import json

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, Session, mapped_column
from app.database import Base, engine

from app.config import settings
from app.keitaro import get_resource, request_resource

creation_lock = asyncio.Lock()


class CreationRequest(Base):
    __tablename__ = "creation_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CampaignCreate(BaseModel):
    request_id: UUID
    name: str = Field(min_length=1, max_length=150)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


async def create_campaign(data: CampaignCreate):
    async with creation_lock:
        key = str(data.request_id)
        payload = json.dumps(data.model_dump(mode="json"), sort_keys=True)
        with Session(engine) as session:
            existing = session.get(CreationRequest, key)
            if existing:
                if existing.payload != payload:
                    raise HTTPException(409, "Этот запрос уже использован с другими данными")
                if existing.result:
                    return existing.result
                raise HTTPException(409, "Предыдущая попытка не завершена. Проверьте кампанию в Keitaro перед созданием новой")
            session.add(CreationRequest(id=key, payload=payload))
            session.commit()
        result = await create_remote_campaign(data)
        with Session(engine) as session:
            row = session.get(CreationRequest, key)
            row.result = result
            session.commit()
        return result


async def create_remote_campaign(data: CampaignCreate):
    if not settings.campaign_prefix.startswith("test_"):
        raise HTTPException(503, "Префикс кампании должен начинаться с test_")
    name = data.name
    if not name.startswith(settings.campaign_prefix):
        name = settings.campaign_prefix + name
    offer = await get_resource(f"offers/{data.offer_id}")
    if offer.get("state") != "active":
        raise HTTPException(422, "Выберите активный оффер")
    campaign = await request_resource("POST", "campaigns", {
        "name": name, "alias": "test-" + uuid4().hex[:16],
        "type": "position", "state": "disabled",
        "domain_id": data.domain_id, "group_id": data.group_id,
        "traffic_source_id": data.traffic_source_id,
    })
    campaign_id = campaign["id"]
    common = {"campaign_id": campaign_id, "type": "regular", "state": "active",
              "collect_clicks": True, "filter_or": False}
    try:
        await request_resource("POST", "streams", {
            **common, "name": f"{data.country} → Google", "position": 1,
            "schema": "redirect", "action_type": "http",
            "action_payload": "https://www.google.com/",
            "filters": [{"name": "country", "mode": "accept", "payload": [data.country]}],
        })
        await request_resource("POST", "streams", {
            **common, "name": "Offers", "position": 2, "schema": "landings",
            "action_type": "http", "action_payload": "",
            "landings": [], "filters": [],
            "offers": [{"offer_id": data.offer_id, "share": 100, "state": "active"}],
        })
        streams = await get_resource(f"campaigns/{campaign_id}/streams")
        if len(streams) != 2:
            raise HTTPException(502, "Не удалось проверить оба потока")
        campaign = await request_resource("PUT", f"campaigns/{campaign_id}", {"state": "active"})
    except HTTPException as error:
        raise HTTPException(502, f"Кампания #{campaign_id} создана выключенной. Настройка не завершена. {error.detail}") from error
    return {"id": campaign_id, "name": name,
            "url": campaign.get("domain", "").rstrip("/") + "/" + campaign["alias"],
            "admin_url": settings.keitaro_base_url.rstrip("/") + f"/admin/#!/campaigns/{campaign_id}"}
