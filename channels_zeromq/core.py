import logging
import string
import random
import json
import asyncio
import collections

from channels.exceptions import ChannelFull
import zmq.asyncio
import zmq

from channels_zeromq.sane_abc import FlushExtension, SanityCheckedGroupLayer
from channels_zeromq.sockets import Publisher, Channel

log = logging.getLogger(__name__)

class ZeroMqGroupLayer(SanityCheckedGroupLayer, FlushExtension):

    def __init__(self, expiry=60, capacity=1000, channel_capacity=1000, group_expiry=86400, **kwargs):
        super().__init__(expiry=expiry, capacity=capacity, channel_capacity=channel_capacity, group_expiry=group_expiry, **kwargs)
        self.zmqctx = zmq.asyncio.Context.instance()
        self.channels = collections.defaultdict(self.make_channel)
        self.publisher = Publisher(self.zmqctx, capacity, expiry)
        # self.log = logging.getLogger('zmq_layer')
        log.debug('finished')
        for k, v in kwargs.items():
            log.warning(f'unparsed config entry: {k}: {v}')

    extensions = ['groups', 'flush']

    def make_channel(self):
        chn = Channel(self.zmqctx, self.capacity)
        return chn

    async def on_receive(self, channel):
        message = await self.channels[channel].receive()
        log.debug(f'message: {message}')
        return message

    async def on_send(self, channel, message: dict):
        log.error('not implemented, not sending!')
        raise NotImplementedError

    async def on_new_channel(self, prefix="specific."):
        rand = ''.join(random.choice(string.ascii_letters) for i in range(12))
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
        try:
            await self.publisher.send_group(group, json.dumps(message))
        except ChannelFull:
            raise

    async def flush(self):
        raise NotImplementedError

    async def close(self):
        self.zmqctx.term()
