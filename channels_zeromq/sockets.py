import logging
import json

from channels.exceptions import ChannelFull
import zmq
import zmq.asyncio
import asyncio

CLIENT_ADDRESS = 'inproc://somename'

log = logging.getLogger(__name__)

class Channel:
    def __init__(self, context: zmq.asyncio.Context, capacity):

        self.socket = context.socket(zmq.SUB)
        self.socket.connect(CLIENT_ADDRESS)
        # high water mark, aka: when to block or drop packets
        self.socket.hwm = capacity
        log.debug(f'finished: {__name__}')

    def subscribe(self, group_name):
        self.socket.subscribe(group_name)
        log.debug('finished')

    async def receive(self):
        msg = str(await self.socket.recv_string())
        log.debug(f'recieved: {msg}')

        group_name, payload = msg.split('|', maxsplit=1)
        log.debug(f'group_name: {group_name}, payload:{payload}')

        decoded_payload = json.loads(payload)
        log.debug(f'decoded_payload:{decoded_payload}')
        return decoded_payload

    def unsubscribe(self, group_name):
        # self.socket.setsockopt_string(zmq.UNSUBSCRIBE, group_name)
        self.socket.unsubscribe(group_name)
        log.debug('unsubscribed')

    def close(self):
        self.socket.close()
        log.debug('closed')


class Publisher:
    TASK_COUNT = 4
    def __init__(self, context, capacity, expiry):
        # log = logging.getLogger(__name__)
        self.socket = context.socket(zmq.PUB)
        self.socket.hwm = capacity
        self.expiry = expiry
        self.socket.bind(CLIENT_ADDRESS)
        self.queue = asyncio.Queue(capacity)
        self.tasks = [asyncio.create_task(self.do_send_group()) for _ in range(self.TASK_COUNT)]

    async def do_send_group(self):
        while True:
            group, message = await self.queue.get()
            if group == 'STOP' and message == 'STOP':
                break
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
                log.error(e)
                pass

    async def send_group(self, group, message):
        try:
            self.queue.put_nowait((group, message))
        except asyncio.QueueFull as e:
            log.error(e)
        # try:
        #     await asyncio.wait_for(
        #         self.socket.send_string(f'{group}|{message}', flags=zmq.NOBLOCK),
        #         timeout=self.expiry)
        # except zmq.error.ZMQError:
        #     """
        #     Sending to a group never raises ChannelFull;
        #     instead, it must silently drop the message if it is over capacity,
        #     as per ASGI’s at-most-once delivery policy.
        #     """
        #     pass

    def close(self):
        self.socket.close()
        for _ in range(self.TASK_COUNT):
            self.queue.put_nowait(('STOP', 'STOP'))
