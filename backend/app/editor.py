import copy
import asyncio
import hashlib
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Integer, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base, engine
from app.keitaro import get_resource, request_resource

router = APIRouter(prefix='/api/editor')
campaign_locks: dict[int, asyncio.Lock] = {}


def campaign_lock(campaign_id):
    return campaign_locks.setdefault(campaign_id, asyncio.Lock())


class CampaignDraft(Base):
    __tablename__ = 'campaign_drafts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict] = mapped_column(JSON)


def signature(stream):
    return hashlib.sha256(json.dumps(stream.get('offers', []), sort_keys=True).encode()).hexdigest()


def distribute(offers):
    active = [offer for offer in offers if not offer['removed']]
    pinned = sum(offer['share'] for offer in active if offer['pinned'])
    free = [offer for offer in active if not offer['pinned']]
    if pinned > 100 or (active and not free and pinned != 100):
        raise HTTPException(422, 'Закреплённые доли должны оставлять возможность распределить 100%')
    for offer in offers:
        if offer['removed']:
            offer['share'] = 0
    if free:
        share, remainder = divmod(100 - pinned, len(free))
        for index, offer in enumerate(free):
            offer['share'] = share + (index >= len(free) - remainder)


def read_draft(campaign_id):
    with Session(engine) as session:
        row = session.get(CampaignDraft, campaign_id)
        if row is None:
            raise HTTPException(404, 'Сначала загрузите кампанию из Keitaro')
        return copy.deepcopy(row.data), row.revision


def save_draft(campaign_id, data, revision):
    with Session(engine) as session:
        changed = session.execute(update(CampaignDraft).where(
            CampaignDraft.id == campaign_id, CampaignDraft.revision == revision
        ).values(data=data, revision=revision + 1))
        if changed.rowcount != 1:
            raise HTTPException(409, 'Данные изменились. Откройте кампанию заново')
        session.commit()
    return {**data, 'revision': revision + 1}


class Action(BaseModel):
    revision: int
    operation: str
    offer_id: int = Field(default=0, ge=0)
    share: int = Field(default=0, ge=0, le=100)


@router.get('/{campaign_id}')
def current(campaign_id: int):
    data, revision = read_draft(campaign_id)
    return {**data, 'revision': revision}


@router.post('/{campaign_id}/fetch')
async def fetch(campaign_id: int):
    async with campaign_lock(campaign_id):
        return await fetch_campaign(campaign_id)


async def fetch_campaign(campaign_id: int):
    campaign = await get_resource(f'campaigns/{campaign_id}')
    streams = await get_resource(f'campaigns/{campaign_id}/streams')
    offers = await get_resource('offers')
    names = {offer['id']: offer['name'] for offer in offers}
    with Session(engine) as session:
        row = session.get(CampaignDraft, campaign_id)
        if row and any(stream['dirty'] for stream in row.data['streams']):
            raise HTTPException(409, 'Перед синхронизацией опубликуйте или отмените черновики')
        old = {stream['id']: stream for stream in row.data['streams']} if row else {}
        result = []
        for stream in streams:
            previous = old.get(stream['id'], {})
            archived = {offer['id']: copy.deepcopy(offer) for offer in previous.get('offers', [])}
            for offer in archived.values():
                offer.update(removed=True, share=0)
            for offer in stream.get('offers', []):
                offer_id = offer['offer_id']
                archived[offer_id] = {
                    'id': offer_id, 'name': names.get(offer_id, f'Оффер #{offer_id}'),
                    'share': offer['share'] if offer.get('state') == 'active' else 0,
                    'removed': offer.get('state') != 'active',
                    'pinned': archived.get(offer_id, {}).get('pinned', False),
                }
            for offer in archived.values():
                if offer['removed']:
                    offer['pinned'] = False
            items = list(archived.values())
            result.append({'id': stream['id'], 'name': stream['name'],
                           'editable': stream.get('schema') == 'landings',
                           'offers': items, 'saved': copy.deepcopy(items),
                           'signature': signature(stream), 'dirty': False})
        data = {'id': campaign_id, 'name': campaign['name'], 'streams': result}
        if row:
            row.data = data
            row.revision += 1
        else:
            row = CampaignDraft(id=campaign_id, data=data, revision=1)
            session.add(row)
        session.commit()
        return {**data, 'revision': row.revision}


@router.post('/{campaign_id}/streams/{stream_id}')
async def action(campaign_id: int, stream_id: int, body: Action):
    async with campaign_lock(campaign_id):
        return await edit_stream(campaign_id, stream_id, body)


async def edit_stream(campaign_id: int, stream_id: int, body: Action):
    data, revision = read_draft(campaign_id)
    if revision != body.revision:
        raise HTTPException(409, 'Данные изменились. Откройте кампанию заново')
    stream = next((item for item in data['streams'] if item['id'] == stream_id), None)
    if stream is None:
        raise HTTPException(404, 'Поток не найден')
    if not stream.get('editable'):
        raise HTTPException(422, 'Этот поток использует перенаправление без офферов')
    offers = stream['offers']
    offer = next((item for item in offers if item['id'] == body.offer_id), None)
    if body.operation == 'cancel':
        stream['offers'] = copy.deepcopy(stream['saved'])
        stream['dirty'] = False
    elif body.operation == 'push':
        remote = await get_resource(f'streams/{stream_id}')
        active = [item for item in offers if not item['removed']]
        if not active or sum(item['share'] for item in active) != 100:
            raise HTTPException(422, 'Для публикации нужен хотя бы один оффер и сумма долей 100%')
        payload = [{'offer_id': item['id'], 'share': item['share'], 'state': 'active'} for item in active]
        expected = sorted((item['offer_id'], item['share']) for item in payload)
        remote_offers = sorted((item['offer_id'], item['share']) for item in remote.get('offers', []))
        if remote['campaign_id'] != campaign_id:
            raise HTTPException(409, 'Поток принадлежит другой кампании')
        if remote_offers != expected:
            if signature(remote) != stream['signature']:
                raise HTTPException(409, 'Поток изменён в Keitaro. Отмените черновик и синхронизируйте данные')
            await request_resource('PUT', f'streams/{stream_id}', {'offers': payload})
        verified = await get_resource(f'streams/{stream_id}')
        expected = sorted((item['offer_id'], item['share']) for item in payload)
        actual = sorted((item['offer_id'], item['share']) for item in verified['offers'])
        if expected != actual:
            raise HTTPException(502, 'Keitaro вернул неожиданный состав офферов. Проверьте поток')
        stream.update(saved=copy.deepcopy(offers), signature=signature(verified), dirty=False)
    else:
        if body.operation == 'equalize':
            for item in offers:
                item['pinned'] = False
        elif body.operation == 'add':
            if offer and not offer['removed']:
                raise HTTPException(422, 'Оффер уже добавлен')
            if offer:
                offer['removed'] = False
            else:
                remote = await get_resource(f'offers/{body.offer_id}')
                if remote.get('state') != 'active':
                    raise HTTPException(422, 'Оффер недоступен')
                offers.append({'id': body.offer_id, 'name': remote['name'], 'share': 0, 'pinned': False, 'removed': False})
        elif offer is None:
            raise HTTPException(404, 'Оффер не найден')
        elif body.operation == 'remove':
            offer.update(removed=True, pinned=False)
        elif body.operation == 'pin':
            offer.update(share=body.share, pinned=True)
        elif body.operation == 'unpin':
            offer['pinned'] = False
        else:
            raise HTTPException(422, 'Неизвестная операция')
        distribute(offers)
        stream['dirty'] = offers != stream['saved']
    return save_draft(campaign_id, data, revision)
