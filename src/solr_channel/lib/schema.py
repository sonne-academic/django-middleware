import json
import dataclasses
import logging
import typing
import inspect
from enum import Enum
from typing import List, Iterable, Callable, Dict

log = logging.getLogger(__name__)
GENERIC_TYPE = type(typing.List)

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


def get_parameters(signature: inspect.Signature) -> List[inspect.Parameter]:
    return [p for p in signature.parameters.values()]


def get_fields(dc) -> List[dataclasses.Field]:
    return dataclasses.fields(dc)


def json_type_generic(cls):
    if type(cls) is not GENERIC_TYPE:
        logging.error(f'unknown or empty parameter annotation: {cls}')
    if cls.__origin__ is list:
        return {'type': 'array', 'items': json_type(cls.__args__[0])}


def json_type_dataclass(cls: dataclasses.dataclass):
    props = {}
    required = []
    for field in get_fields(cls):
        props[field.name] = json_type(field.type)
        if field.default is dataclasses.MISSING:
            required.append(field.name)
    if 0 < len(required):
        return {'type': 'object', 'properties': props, 'required': required}
    return {'type': 'object', 'properties': props}


def json_type(cls):
    if cls is str:
        return {'type': 'string'}
    elif cls is int:
        return {'type': 'integer'}
    elif cls is float:
        return {'type': 'number'}
    elif cls is dict:
        return {'type': 'object'}
    elif cls is list:
        return {'type': 'array'}
    elif cls is bool:
        return {'type': 'boolean'}
    elif str(cls).startswith('typing.'):
        return json_type_generic(cls)
    elif issubclass(cls, Enum):
        return {'enum': list(cls.__members__.keys())}
    elif dataclasses.is_dataclass(cls):
        return json_type_dataclass(cls)
    else:
        logging.error(f'unknown or empty parameter annotation: {cls}')
        return {}


def make_json_schema(decorated_fn: Callable, argdoc: Dict[str, str]):
    signature = inspect.signature(decorated_fn)
    if signature is None:
        return
    _cls, func_name = decorated_fn.__qualname__.split('.')
    schema = {'type': 'object', 'properties': [], 'description': inspect.getdoc(decorated_fn)}
    props = {}
    required = []
    params = get_parameters(signature)
    for parameter in get_parameters(signature):
        if 'self' == parameter.name:
            continue
        if 'rqid' == parameter.name:
            continue
        prop = {}
        try:
            prop['description'] = argdoc[parameter.name]
        except KeyError:
            logging.error(f'no documentation for: {parameter.name}')
        prop.update(json_type(parameter.annotation))

        if parameter.default is inspect.Parameter.empty:
            required.append(parameter.name)
        else:
            prop['default'] = parameter.default
        props[parameter.name] = prop
    schema['properties'] = props
    if 0 != len(required):
        schema['required'] = required
    ret = signature.return_annotation
    if ret is not inspect.Parameter.empty and type(ret) is GENERIC_TYPE:
        log.info(json.dumps(json_type(ret), indent=2))
        return {'parameters': schema, 'returns': json_type(ret)}

    return {'parameters': schema}


def make_json_schema_dc(decorated_fn: Callable, argdoc: Dict[str, str]):
    signature = inspect.signature(decorated_fn)
    if signature is None:
        return
    _cls, func_name = decorated_fn.__qualname__.split('.')
    schema = {'type': 'object', 'properties': [], 'description': inspect.getdoc(decorated_fn)}
    props = {}
    required = []
    params = get_parameters(signature)
    if 2 != len(params):
        log.error(f'function must take exactly one argunemt, but it has {len(params)-1}')
    para = params[1]
    if not dataclasses.is_dataclass(para.annotation):
        log.error(f'parameter must be a dataclass')
        return {}
    for field in get_fields(para.annotation):
        if 'rqid' == field.name:
            continue
        if 'type' == field.name:
            continue
        prop = {}
        try:
            prop['description'] = argdoc[field.name]
        except KeyError:
            logging.error(f'no documentation for: {field.name}')
        prop.update(json_type(field.type))
        if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING:
            required.append(field.name)
        elif field.default is not dataclasses.MISSING:
            prop['default'] = field.default
        props[field.name] = prop

    schema['properties'] = props
    if 0 != len(required):
        schema['required'] = required
    ret = signature.return_annotation
    if ret is not inspect.Parameter.empty and type(ret) is GENERIC_TYPE:
        log.info(json.dumps(json_type(ret), indent=2))
        return {'parameters': schema, 'returns': json_type(ret)}

    return {'parameters': schema}

