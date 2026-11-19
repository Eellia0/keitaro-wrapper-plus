from fastapi import APIRouter, Query
from app.keitaro import get_resource

router = APIRouter(prefix='/api')

@router.get('/campaign-search')
async def search_campaigns(q: str = Query(default='', max_length=150)):
    matches = []
    offset = 0
    limit = 100
    while True:
        page = await get_resource(f'campaigns?limit={limit}&offset={offset}')
        for campaign in page:
            if campaign.get('state') != 'deleted' and q.casefold().strip() in f"{campaign['id']} {campaign['name']}".casefold():
                matches.append({'id': campaign['id'], 'name': campaign['name']})
        if len(page) < limit:
            break
        offset += limit
    return matches
