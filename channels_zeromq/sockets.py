import asyncio
import json
import logging

import zmq
import zmq.asyncio

log = logging.getLogger(__name__)


class Channel:
    def __init__(self, host, context: zmq.asyncio.Context, capacity):
        self.socket = context.socket(zmq.SUB)
        self.socket.connect(host)
        # high water mark, aka: when to block or drop packets
        self.socket.hwm = capacity
        self.queue = asyncio.Queue(capacity)
        self.task = asyncio.create_task(self._group_receive())
        log.debug(f'finished: {__name__}')

    async def receive(self):
        payload = await self.queue.get()
        decoded_payload = json.loads(payload)
        log.debug(f'decoded_payload:{decoded_payload}')
        self.queue.task_done()
        return decoded_payload

    async def _group_receive(self):
        while True:
            msg = str(await self.socket.recv_string())
            if msg == 'STOP':
                break
            log.debug(f'recieved: {msg}')

            group_name, payload = msg.split('|', maxsplit=1)
            log.debug(f'group_name: {group_name}, payload:{payload}')
            try:
                self.queue.put_nowait(payload)
            except asyncio.QueueFull as e:
                log.exception(e)

    async def send(self, message: str):
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull as e:
            log.exception(e)

    def subscribe(self, group_name):
        self.socket.subscribe(group_name)
        log.debug(f'subscribed {group_name}')

    def unsubscribe(self, group_name):
        self.socket.unsubscribe(group_name)
        log.debug(f'unsubscribed {group_name}')

    def close(self):
        log.info('stopping worker')
        self.queue.put_nowait('STOP')
        log.info('joining queue')
        self.queue.join()
        log.info('closing socket')
        self.socket.close()
        log.debug('closed')


class Publisher:
    TASK_COUNT = 4

    def __init__(self, host, context, capacity, expiry):
        self.socket = context.socket(zmq.PUB)
        self.socket.hwm = capacity
        self.expiry = expiry
        self.socket.bind(host)
        self.queue = asyncio.Queue(capacity)
        self.tasks = [asyncio.create_task(self._send_group()) for _ in range(self.TASK_COUNT)]

    async def _send_group(self):
        while True:
            group, message = await self.queue.get()
            try:
                await asyncio.wait_for(
                    self.socket.send_string(f'{group}|{message}', flags=zmq.NOBLOCK),
                    timeout=self.expiry)
            except zmq.error.ZMQError as e:
                """
                Sending to a group never raises ChannelFull; 
                instead, it must silently drop the message if it is over capacity, 
                as per ASGI’s at-most-once delivery policy.
                """
                log.exception(e)
            self.queue.task_done()
            if group == 'STOP' and message == 'STOP':
                break

    async def send_group(self, group: str, message: str):
        try:
            self.queue.put_nowait((group, message))
        except asyncio.QueueFull as e:
            log.exception(e)

    def close(self):
        log.info(f'stopping workers')
        for _ in range(self.TASK_COUNT):
            self.queue.put_nowait(('STOP', 'STOP'))
        log.info('gathering workers')
        asyncio.gather(*self.tasks)
        log.info('join queue')
        self.queue.join()
        log.info('closing socket')
        self.socket.close()
        log.info('closed')
