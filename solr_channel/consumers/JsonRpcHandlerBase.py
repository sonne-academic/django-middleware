import dataclasses
import inspect
import logging
from enum import Enum
from typing import Dict, Iterable
from solr_channel.lib.schema import make_json_schema, make_json_schema_dc, get_parameters
from functools import wraps

from django.conf import settings

from .JsonRpcConsumer import JsonRpcConsumer, JsonRpcRequest, JsonRpcResultResponse
from .JsonRpcExceptions import *

__all__ = ['JsonRpcHandlerBase', 'command', 'chn_command', 'Availability']
log = logging.getLogger(__name__)


class Availability(Enum):
    DEBUG_ONLY = 'DEBUG_ONLY'
    PRODUCTION = 'PRODUCTION'


class JsonRpcHandlerBase(JsonRpcConsumer):
    commands = {}
    chn_commands = {}

    @classmethod
    def command(cls, availability: Availability, argdoc: Dict[str, str] = None, returns=None):
        def register_func(decorated_fn):
            if not settings.DEBUG and availability == Availability.DEBUG_ONLY:
                log.error(f'ignoring debug only function: {decorated_fn.__qualname__}')
                return decorated_fn
            if not inspect.iscoroutinefunction(decorated_fn):
                err = f'commands must be async, but {decorated_fn.__qualname__} is not.'
                err += f' its type is {type(decorated_fn)}'
                log.error(err)
            _cls, func_name = decorated_fn.__qualname__.split('.')
            if _cls not in cls.commands:
                cls.commands[_cls] = {}
            schema = make_json_schema(decorated_fn, argdoc)
            cls.commands[_cls][func_name] = schema
            log.info(schema)
            return decorated_fn

        return register_func

    @classmethod
    def chn_command(cls, availability: Availability, argdoc: Dict[str, str] = None):
        def register_func(decorated_fn):
            @wraps(decorated_fn)
            async def type_wrapper(self: JsonRpcHandlerBase, event: dict):
                rqid = event.get('rqid', None)
                _, p = get_parameters(inspect.signature(decorated_fn))
                dcls = p.annotation
                try:
                    dc = dcls(**event)
                except TypeError as e:
                    log.exception(e)
                    log.error(str(event))
                    await self.handle_exception(JsonRpcInvalidParams(str(e)), rqid)
                    return
                try:
                    result = await decorated_fn(self, dc)
                    await self.send_result(result, rqid)
                    return
                except Exception as e:
                    return await self.handle_exception(e, rqid)

            if availability == Availability.DEBUG_ONLY and not settings.DEBUG:
                log.warning(f'ignoring debug only function: {decorated_fn.__qualname__}')
                return decorated_fn
            if not inspect.iscoroutinefunction(decorated_fn):
                err = f'commands must be async, but {decorated_fn.__qualname__} is not.'
                err += f' its type is {type(decorated_fn)}'
                log.error(err)
            _cls_name, func_name = decorated_fn.__qualname__.split('.')
            if _cls_name not in cls.chn_commands:
                cls.chn_commands[_cls_name] = {}
            schema = make_json_schema_dc(decorated_fn, argdoc)
            cls.chn_commands[_cls_name][func_name] = schema
            log.info(schema)
            return type_wrapper

        return register_func

    @property
    def _commands(self) -> dict:
        name = self.__class__.__name__
        return self.commands.get(name, {})

    @property
    def _chn_commands(self) -> dict:
        name = self.__class__.__name__
        return self.chn_commands.get(name, {})

    async def handle_exception(self, e, msg_id: str):
        log.exception(e)
        if issubclass(type(e),JsonRpcException):
            await self.send_error(e,msg_id)
        else:
            await self.send_error(JsonRpcInternalError('something bad happened!!!!'),msg_id)
        pass

    async def respond(self, request, awaitable):
        async for result in awaitable:
            await self.send_response(JsonRpcResultResponse(result, request.id))

    async def handle_request(self, request: JsonRpcRequest):
        if 'help' == request.method:
            await self.send_response(JsonRpcResultResponse(self._commands, request.id))
            return

        if request.method not in self._commands and request.method not in self._chn_commands:
            raise JsonRpcMethodNotFound(f'no such method: {request.method}. use "help" to request available methods')
        if not isinstance(request.params, dict):
            raise JsonRpcInvalidParams(f'params must be an object')

        if request.method in self._commands:
            async_fun = getattr(self, request.method)
            params = request.params
            params['rqid'] = request.id
            try:
                awaitable = async_fun(**params)
            except TypeError as e:
                raise JsonRpcInvalidParams(str(e))
            await awaitable
            return

        if request.method in self._chn_commands:
            await self.channel_layer.send(self.channel_name, {
                'type': request.method,
                'rqid': request.id,
                **request.params
            })


command = JsonRpcHandlerBase.command
chn_command = JsonRpcHandlerBase.chn_command