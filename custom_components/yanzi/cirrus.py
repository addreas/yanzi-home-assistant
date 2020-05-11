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

        self.consumers = []
        self.producer = asyncio.create_task(self.producer())

    async def producer(self):
        try:
            while True:
                res = await self.ws.recv()
                for q in self.consumers:
                    await q.put(res)
        except websockets.ConnectionClosedOK:
            pass

    async def send_json(self, message):
        await self.ws.send(json.dumps(message))

    async def send_binary(self, message):
        await self.ws.send(message)

    async def _watch(self, timeout):
        q = asyncio.Queue()
        self.consumers.append(q)
        try:
            while True:
                yield await asyncio.wait_for(q.get(), timeout)
        finally:
            self.consumers.remove(q)

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
        session_id = response.get('sessionId')
        self.session_id = session_id
        return session_id

    async def subscribe(self, subscribe_request):
        async def send_subscribe():
            response = await self.request(subscribe_request)
            if response['responseCode']['name'] != 'success':
                raise RuntimeError(f'Error when sending SubscribeRequest to cirrus: {response}')
            delay = response['expireTime'] / 1000 - time.time()
            log.debug(
                'Sending next subscribe request in %d seconds. (%d minutes)', delay, delay / 60)
            await asyncio.sleep(delay)
            await send_subscribe()

        subscription_task = asyncio.create_task(send_subscribe())

        try:
            async for message in self.watch():
                if message['messageType'] == 'SubscribeData':
                    yield message
                if subscription_task:
                    raise subscription_task.exception()
        finally:
            subscription_task.cancel()
            log.debug('Exiting subscription')
