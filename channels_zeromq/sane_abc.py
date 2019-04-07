from channels.layers import BaseChannelLayer, InMemoryChannelLayer
import abc


class FlushExtension(abc.ABC):
    @abc.abstractmethod
    async def flush(self):
        pass

    @abc.abstractmethod
    async def close(self):
        pass


class SanityCheckedLayer(abc.ABC, BaseChannelLayer):
    def __init__(self, expiry=60, capacity=100, channel_capacity=None):
        super().__init__(expiry=expiry, capacity=capacity, channel_capacity=channel_capacity)

    async def receive(self, channel):
        assert self.valid_channel_name(channel)
        return await self.on_receive(channel)

    async def new_channel(self, prefix="specific."):
        return await self.on_new_channel(prefix)

    async def send(self, channel: str, message: dict):
        assert isinstance(message, dict), "message is not a dict"
        assert self.valid_channel_name(channel), "Channel name not valid"
        # If it's a process-local channel, strip off local part and stick full name in message
        assert "__asgi_channel__" not in message
        await self.on_send(channel, message)

    @abc.abstractmethod
    async def on_receive(self, channel):
        pass

    @abc.abstractmethod
    async def on_send(self, channel, message: dict):
        pass

    @abc.abstractmethod
    async def on_new_channel(self, prefix="specific."):
        pass


class SanityCheckedGroupLayer(SanityCheckedLayer):
    def __init__(self, expiry=60, capacity=1000, channel_capacity=None, group_expiry=86400, **kwargs):
        super().__init__(expiry=expiry, capacity=capacity, channel_capacity=channel_capacity)
        self.group_expiry = group_expiry

    async def group_add(self, group, channel):
        assert self.valid_group_name(group), "Group name not valid"
        assert self.valid_channel_name(channel), "Channel name not valid"
        await self.on_group_add(group, channel)

    async def group_discard(self, group, channel):
        assert self.valid_channel_name(channel), "Invalid channel name"
        assert self.valid_group_name(group), "Invalid group name"
        await self.on_group_discard(group, channel)

    async def group_send(self, group, message):
        assert isinstance(message, dict), "Message is not a dict"
        assert self.valid_group_name(group), "Invalid group name"
        await self.on_group_send(group, message)

    @abc.abstractmethod
    async def on_group_add(self, group, channel):
        pass

    @abc.abstractmethod
    async def on_group_discard(self, group, channel):
        pass

    @abc.abstractmethod
    async def on_group_send(self, group, message):
        pass
