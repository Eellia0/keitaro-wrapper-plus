from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.keitaro import get_resource
from app.campaigns import CampaignCreate, create_campaign
from app.editor import router as editor_router
from app.search import router as search_router

app = FastAPI(title="Keitaro Wrapper", version="0.1.0")
app.include_router(editor_router)
app.include_router(search_router)


@app.get("/api/domains")
async def domains():
    return await get_resource("domains")


@app.get("/api/groups")
async def groups():
    return await get_resource("groups?type=campaigns")


@app.get("/api/offers")
async def offers():
    data = await get_resource("offers")
    return [{"id": item["id"], "name": item["name"]}
            for item in data if item.get("state") == "active"]


@app.get("/api/settings")
def public_settings():
    return {"campaign_prefix": settings.campaign_prefix}


@app.post("/api/campaigns", status_code=201)
async def campaigns(data: CampaignCreate):
    return await create_campaign(data)


@app.get("/api/traffic-sources")
async def traffic_sources():
    return await get_resource("traffic_sources")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(503, "База данных недоступна") from error
    return {
        "status": "ok",
        "database": "ok",
        "keitaro_configured": bool(
            settings.keitaro_base_url and settings.keitaro_api_key
        ),
    }

