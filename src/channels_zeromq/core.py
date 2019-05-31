import collections
import json
import logging
import random
import string
import asyncio
from typing import Dict
from twisted.internet import reactor
import zmq
import zmq.asyncio
from channels.http import async_to_sync

from channels_zeromq.sane_abc import FlushExtension, SanityCheckedGroupLayer
from channels_zeromq.sockets import Publisher, Channel

log = logging.getLogger(__name__)


class ZeroMqGroupLayer(SanityCheckedGroupLayer, FlushExtension):

    def __init__(self, host='inproc://somename', expiry=60, capacity=1000, channel_capacity=1000, group_expiry=86400, **kwargs):
        super().__init__(expiry=expiry, capacity=capacity, channel_capacity=channel_capacity, group_expiry=group_expiry,
                         **kwargs)
        self.zmqctx = zmq.asyncio.Context.instance()
        self.host = host
        self.channels: Dict[str, Channel] = collections.defaultdict(self.make_channel)
        self.publisher = Publisher(self.host , self.zmqctx, capacity, expiry)
        reactor.addSystemEventTrigger('before', 'shutdown', self.shutdown)
        for k, v in kwargs.items():
            log.warning(f'unparsed config entry: {k}: {v}')

    extensions = ['groups', 'flush']

    def make_channel(self):
        chn = Channel(self.host, self.zmqctx, self.capacity)
        return chn

    def shutdown(self):
        log.error('shutdown hook tripped')
        loop=asyncio.get_event_loop()
        loop.run_until_complete(self.close())
        log.error('shutdown hook done')

    async def on_receive(self, channel: str):
        message = await self.channels[channel].receive()
        log.debug(f'message: {message}')
        return message

    async def on_send(self, channel: str, message: dict):
        await self.channels[channel].send(json.dumps(message))

    async def on_new_channel(self, prefix="specific."):
        rand = ''.join(random.choice(string.ascii_letters) for _ in range(12))
        channel = f'{prefix}.zmq!{rand}'
        log.info(f'channel: [{channel}]')
        if len(self.channels) <= self.channel_capacity:
            return channel
        raise NotImplementedError(f'clean your channels, yo!')

    async def on_group_add(self, group, channel):
        log.debug(f'group: [{group}] channel: [{channel}]')
        self.channels[channel].subscribe(group)

    async def on_group_discard(self, group, channel):
        log.debug(f'group: [{group}] channel: [{channel}]')
        self.channels[channel].unsubscribe(group)

    async def on_group_send(self, group, message):
        log.info(f'group: [{group}] message: [{message}]')
        await self.publisher.send_group(group, json.dumps(message))

    async def flush(self):
        raise NotImplementedError

    async def close(self):
        log.info('closing zmq layer')
        self.publisher.close()
        for channel in self.channels.values():
            channel.close()

        self.zmqctx.term()
        log.info('closed zmq layer')
