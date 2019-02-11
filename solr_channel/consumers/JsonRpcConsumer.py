from abc import abstractmethod
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from dataclasses import dataclass, field, asdict
from typing import Union

from .JsonRpcExceptions import *


@dataclass
class JsonRpcRequest:
    jsonrpc: str
    method: str
    id: Union[str, int]
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        if '2.0' != self.jsonrpc:
            raise JsonRpcInvalidRequest(f'only jsonrpc 2.0 is supported, you sent {self.jsonrpc}')
        if type(id) is str and self.method.startswith('rpc.'):
            raise JsonRpcInvalidRequest(f'you may not call internal RPC methods (methods starting with "rpc.")')

@dataclass
class JsonRpcErrorResponse:
    error: dict
    id: Union[str, int]  # can be none, tho.
    jsonrpc: str = '2.0'


@dataclass
class JsonRpcResultResponse:
    result: dict
    id: Union[str, int]
    jsonrpc: str = '2.0'


async def build_request(text_data):
    if not text_data:
        raise JsonRpcInvalidRequest('No text section for incoming WebSocket frame!')
    try:
        payload = await JsonRpcConsumer.decode_json(text_data)
    except json.decoder.JSONDecodeError as e:
        raise JsonRpcParseError(f'malformed JSON request: {str(e)}', data=e.__dict__)

    missing_fields = list(filter(lambda x: x not in payload, ('jsonrpc', 'method', 'id')))
    if not 0 == len(missing_fields):
        raise JsonRpcInvalidRequest(f'missing mandatory parameter(s) {missing_fields}')
    try:
        return JsonRpcRequest(**payload)  # could raise type error if payload contains more data then expected
    except TypeError as e:
        raise JsonRpcInvalidRequest(f'wrong parameters {e}')


class JsonRpcConsumer(AsyncWebsocketConsumer):
    """
    Variant of AsyncWebsocketConsumer that automatically JSON-encodes and decodes
    messages as they come in and go out. Expects everything to be text; will
    error on binary data.
    """

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        try:
            request = await build_request(text_data)
        except JsonRpcException as e:
            await self.send_error(e,None)
            return

        try:
            await self.handle_request(request)
        except JsonRpcException as e:
            await self.send_error(e, request.id)
            return

    async def send_error(self, exception: JsonRpcException, msg_id):
        await self.send_json(asdict(JsonRpcErrorResponse(exception.error, msg_id)))

    async def send_response(self, response: JsonRpcResultResponse):
        logging.debug(response)
        await self.send_json(asdict(response))

    @abstractmethod
    async def handle_request(self, request: JsonRpcRequest):
        """
        handle the request
        :param request:
        :return:
        """
        pass

    async def send_json(self, content, close=False):
        """
        Encode the given content as JSON and send it to the client.
        """
        await super().send(
            text_data=await self.encode_json(content),
            close=close,
        )

    @classmethod
    async def decode_json(cls, text_data):
        return json.loads(text_data)

    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content)
