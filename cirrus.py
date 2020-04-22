import asyncio
import ssl
import json
import time
import contextlib
import logging

import websockets
log = logging.getLogger(__name__)

@contextlib.asynccontextmanager
async def connect(uri, **kwargs):
    async with websockets.connect(uri, **kwargs) as ws:
        ws._uri = uri
        yield Cirrus(ws)

class Cirrus:
    def __init__(self, ws):
        self.ws = ws
        self._current_message_id = 0
        self.watchers = 0

    async def send_json(self, message):
        log.debug('sending on %s: %s' self.ws._uri, message)
        await self.ws.send(json.dumps(message))

    async def send_binary(self, message):
        await self.ws.send(message)

    async def _watch(self, timeout):
        self.watchers += 1
        log.debug('currently %d watchers for %s', self.watchers, self.ws._uri)
        try:
            while True:
                    yield await asyncio.wait_for(self.ws.recv(), timeout)
        finally:
            self.watchers -= 1
            log.debug('finally %d watchers for %s', self.watchers, self.ws._uri)

    async def watch(self, timeout=None):
        async for message in self._watch(timeout):
            if type(message) is str:
                # log.debug(message)
                yield json.loads(message)

    async def watch_binary(self, timeout=None):
        async for message in self._watch(timeout):
            if type(message) is bytes:
                yield message

    async def send(self, request, timeout=30):
        message_id = self._current_message_id
        self._current_message_id += 1
        extended_request = {
            **request,
            'messageIdentifier': {
                'resourceType': 'MessageIdentifier',
                'messageId': str(message_id)
            }
        }

        await self.send_json(extended_request)

        response_count = 0
        try:
            async for response in self.watch(timeout):
                if response['messageIdentifier']['messageId'] == str(message_id):
                    response_count += 1
                    yield response

        except asyncio.TimeoutError as e:
            if response_count == 0:
                raise e

    async def request(self, request, timeout=5):
        async for response in self.send(request, timeout):
            return response

    async def authenticate(self, credentials):
        response = await self.request({'messageType': 'LoginRequest', **credentials})
        assert response['responseCode']['name'] == 'success'
        self.session_id = response['sessionId']
        return response['sessionId']

    async def subscribe(self, subscribe_request):
        log.debug('called subscribe for %s', self.ws._uri)
        async def send_subscribe():
            response = await self.request(subscribe_request)
            assert response['responseCode']['name'] == 'success'
            await asyncio.sleep(response['expireTime']/1000 - time.time())
            await asyncio.create_task(send_subscribe())

        subscription_task = asyncio.create_task(send_subscribe())

        try:
            async for message in self.watch():
                if message['messageType'] == 'SubscribeData':
                    log.debug('SubscribeData from %s', self.ws._uri)
                    yield message
        except Exception as e:
            subscription_task.cancel()
            raise e

        log.debug('Exiting subscription')
