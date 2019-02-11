from .JsonRpcExceptions import *
from .JsonRpcConsumer import JsonRpcConsumer, JsonRpcRequest, JsonRpcResultResponse
import logging
import inspect
from typing import Dict, Iterable, Callable
from enum import Enum
import asyncio

__all__ = ['JsonRpcHandlerBase', 'command']


def get_parameters(signature: inspect.Signature) -> Iterable[inspect.Parameter]:
    for parameter in signature.parameters.values():
        yield parameter


# 6.1.1. type
# ("null", "boolean", "object", "array", "number", or "string"), or "integer"
type_map = {
    str: 'string',
    int: 'integer',
    float: 'number',
    bool: 'boolean',
    list: 'array',
    dict: 'object',
    type(None): 'null'
}


def make_json_schema(decorated_fn: Callable, argdoc: Dict[str, str]):
    signature = inspect.signature(decorated_fn)
    _cls, func_name = decorated_fn.__qualname__.split('.')
    schema = {'type': 'object', 'properties': [], 'description': inspect.getdoc(decorated_fn)}
    props = {}
    required = []
    for parameter in get_parameters(signature):
        if 'self' == parameter.name:
            continue
        prop = {}
        try:
            prop['description'] = argdoc[parameter.name]
        except KeyError:
            logging.error(f'no documentation for: {parameter.name}')

        if parameter.annotation is str:
            prop['type'] = 'string'
        elif parameter.annotation is int:
            prop['type'] = 'integer'
        elif parameter.annotation is float:
            prop['type'] = 'number'
        elif parameter.annotation is dict:
            prop['type'] = 'object'
        elif parameter.annotation is list:
            prop['type'] = 'array'
        elif issubclass(parameter.annotation, Enum):
            prop['enum'] = list(parameter.annotation.__members__.keys())
        elif parameter.annotation is bool:
            prop['type'] = 'boolean'
        else:
            logging.error(f'unknown or empty parameter annotation: {parameter.annotation}')

        if parameter.default is inspect.Parameter.empty:
            required.append(parameter.name)
        else:
            prop['default'] = parameter.default
        props[parameter.name] = prop
    schema['properties'] = props
    if 0 != len(required):
        schema['required'] = required
    return {func_name: schema}


class JsonRpcHandlerBase(JsonRpcConsumer):
    log = logging.getLogger('JsonRpcHandler')
    commands = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasks = []

    @classmethod
    def command(cls, help_text: str, argdoc: Dict[str, str] = None):
        def register_func(decorated_fn):
            if not inspect.isasyncgenfunction(decorated_fn):
                err = f'commands must be async generator function, but {decorated_fn.__qualname__} is not. it is {type(decorated_fn)}'
                raise NotImplementedError(err)
            _cls, func_name = decorated_fn.__qualname__.split('.')
            if _cls not in cls.commands:
                cls.commands[_cls] = {}
            cls.commands[_cls][func_name] = (help_text, argdoc)
            schema = make_json_schema(decorated_fn, argdoc)
            print(schema)
            return decorated_fn

        return register_func

    def _commands(self) -> dict:
        name = self.__class__.__name__
        return self.commands.get(name, {})

    async def respond(self, request, awaitable):
        async for result in awaitable:
            await self.send_response(JsonRpcResultResponse(result, request.id))

    async def handle_request(self, request: JsonRpcRequest):
        if request.method not in self._commands() and not 'help' == request.method:
            raise JsonRpcMethodNotFound(f'no such method: {request.method}. use "help" to request available methods')
        if not isinstance(request.params, dict):
            raise JsonRpcInvalidParams(f'params must be an object or null')

        if 'help' == request.method:
            await self.send_response(JsonRpcResultResponse(self._commands(), request.id))
            return

        async_gen = getattr(self, request.method)
        try:
            awaitable = async_gen(**request.params)
        except TypeError as e:
            raise JsonRpcInvalidParams(str(e))
        # TODO: periodically collect tasks and exceptions
        # self.tasks.append(asyncio.create_task(self.respond(request, awaitable)))
        async for result in awaitable:
            await self.send_response(JsonRpcResultResponse(result, request.id))


command = JsonRpcHandlerBase.command
