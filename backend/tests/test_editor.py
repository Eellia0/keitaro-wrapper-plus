import copy
import unittest
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from app.database import Base
from app import editor, campaigns
from fastapi import HTTPException

class EditorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db_patch = patch.object(editor, 'engine', self.engine)
        self.db_patch.start()
        self.remote = {'id': 10, 'campaign_id': 1, 'name': 'Offers', 'schema': 'landings', 'offers': [{'offer_id': 101, 'share': 100, 'state': 'active'}]}
        async def get(path):
            if path == 'campaigns/1': return {'name': 'test_campaign'}
            if path == 'campaigns/1/streams': return [copy.deepcopy(self.remote)]
            if path == 'streams/10': return copy.deepcopy(self.remote)
            if path == 'offers': return [{'id': 101, 'name': 'One'}, {'id': 102, 'name': 'Two'}]
            if path == 'offers/102': return {'id': 102, 'name': 'Two', 'state': 'active'}
            raise AssertionError(path)
        async def put(method, path, payload):
            self.assertEqual((method, path), ('PUT', 'streams/10'))
            self.remote['offers'] = payload['offers']
            return copy.deepcopy(self.remote)
        self.get_patch = patch.object(editor, 'get_resource', get)
        self.put_patch = patch.object(editor, 'request_resource', put)
        self.get_patch.start()
        self.put_patch.start()

    async def asyncTearDown(self):
        self.db_patch.stop()
        self.get_patch.stop()
        self.put_patch.stop()
        self.engine.dispose()

    async def test_draft_push_external_removal_and_restore(self):
        data = await editor.fetch(1)
        async def act(operation, oid=0):
            nonlocal data
            data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation=operation, offer_id=oid))
        await act('add', 102)
        self.assertEqual([o['share'] for o in data['streams'][0]['offers']], [50, 50])
        self.assertEqual(len(self.remote['offers']), 1)
        self.assertTrue(editor.current(1)['streams'][0]['dirty'])
        await act('cancel')
        self.assertEqual(len(data['streams'][0]['offers']), 1)
        await act('add', 102)
        await act('push')
        self.assertEqual(len(self.remote['offers']), 2)
        self.remote['offers'] = [{'offer_id': 101, 'share': 100, 'state': 'active'}]
        data = await editor.fetch(1)
        archived = next(o for o in data['streams'][0]['offers'] if o['id'] == 102)
        self.assertTrue(archived['removed'])
        await act('add', 102)
        await act('push')
        self.assertEqual(len(self.remote['offers']), 2)

    async def test_externally_removed_pinned_offer_can_be_restored(self):
        data = await editor.fetch(1)
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='pin', offer_id=101, share=100))
        await editor.action(1, 10, editor.Action(revision=data['revision'], operation='push'))
        self.remote['offers'] = []
        data = await editor.fetch(1)
        self.assertFalse(data['streams'][0]['offers'][0]['pinned'])
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='add', offer_id=101))
        self.assertEqual(data['streams'][0]['offers'][0]['share'], 100)

    async def test_equalize_unpins_and_can_be_cancelled(self):
        data = await editor.fetch(1)
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='add', offer_id=102))
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='pin', offer_id=101, share=25))
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='push'))
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='equalize'))
        offers = data['streams'][0]['offers']
        self.assertEqual([offer['share'] for offer in offers], [50, 50])
        self.assertFalse(any(offer['pinned'] for offer in offers))
        self.assertEqual(self.remote['offers'][0]['share'], 25)
        data = await editor.action(1, 10, editor.Action(revision=data['revision'], operation='cancel'))
        self.assertEqual(data['streams'][0]['offers'][0]['share'], 25)
        self.assertTrue(data['streams'][0]['offers'][0]['pinned'])

    async def test_stale_revision_and_remote_conflict(self):
        data = await editor.fetch(1)
        await editor.action(1, 10, editor.Action(revision=data['revision'], operation='add', offer_id=102))
        with self.assertRaises(HTTPException) as caught:
            await editor.action(1, 10, editor.Action(revision=data['revision'], operation='cancel'))
        self.assertEqual(caught.exception.status_code, 409)
        self.remote['offers'][0]['share'] = 90
        data = editor.current(1)
        with self.assertRaises(HTTPException) as caught:
            await editor.action(1, 10, editor.Action(revision=data['revision'], operation='push'))
        self.assertEqual(caught.exception.status_code, 409)

    async def test_creation_request_is_idempotent(self):
        calls = []
        async def create(data):
            calls.append(data)
            return {'id': 42, 'name': 'test_campaign'}
        data = campaigns.CampaignCreate(request_id=uuid4(), name='campaign', country='AU', offer_id=101, domain_id=1, group_id=1, traffic_source_id=1)
        with patch.object(campaigns, 'engine', self.engine), patch.object(campaigns, 'create_remote_campaign', create):
            first = await campaigns.create_campaign(data)
            second = await campaigns.create_campaign(data)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)
