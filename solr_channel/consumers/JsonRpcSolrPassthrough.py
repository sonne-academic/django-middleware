from .JsonRpcHandlerBase import JsonRpcHandlerBase, command
from .JsonRpcExceptions import JsonRpcInvalidParams, JsonRpcInternalError
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientConnectionError
from json.decoder import JSONDecodeError
from enum import Enum
import logging
import asyncio
from django.conf import settings

API = f'{settings.SOLR_HOST}/api'
SOLR = f'{settings.SOLR_HOST}/solr'
log = logging.getLogger('JsonRpcSolrPassthrough')

class Method(Enum):
    DELETE = "DELETE"
    PUT = "PUT"
    GET = "GET"
    POST = "POST"


class JsonRpcSolrPassthrough(JsonRpcHandlerBase):
    async def connect(self):
        conn = TCPConnector(limit=30)
        self.http = ClientSession(connector=conn)
        return await super().connect()

    async def disconnect(self, code):
        await self.http.close()
        return await super().disconnect(code)

    async def get_result_api(self, endpoint: str, method: str, payload: dict) -> dict:
        async with ClientSession() as sess:
            if "DELETE" == method:
                async with sess.delete(endpoint, json=payload) as response:
                    return await response.json()
            if "PUT" == method:
                async with sess.put(endpoint, json=payload) as response:
                    return await response.json()
            if "GET" == method:
                async with sess.get(endpoint, json=payload) as response:
                    return await response.json()
            if "POST" == method:
                async with sess.post(endpoint, json=payload) as response:
                    return await response.json()

    async def get_result_solr(self, endpoint: str, method: str, params: dict) -> dict:
        async with ClientSession() as sess:
            if "DELETE" == method:
                async with sess.delete(endpoint, params=params) as response:
                    return await response.json()
            if "PUT" == method:
                async with sess.put(endpoint, params=params) as response:
                    return await response.json()
            if "GET" == method:
                async with sess.get(endpoint, params=params) as response:
                    return await response.json()
            if "POST" == method:
                async with sess.post(endpoint, params=params) as response:
                    return await response.json()

    @command('send a command to the solr api', {
        'endpoint': 'the endpoint of the api: i.e. "/collections"',
        'method': 'one of [DELETE, PUT, GET, POST]',
        'payload': 'the parameters of the command, send an empty object for GET requests',
        'return': 'the result of the response'
    })
    async def pass_through(self, endpoint: str, method: Method, payload: dict):
        log.debug(f'{method}: {endpoint} {payload}')
        if isinstance(method, Method):
            method = method.value
        if method not in Method.__members__:
            raise JsonRpcInvalidParams(f'unsupported method: {method}, must be one of [DELETE, PUT, GET, POST]')
        yield {'responseHeader': {'status': 'accept'}}
        try:
            result = await self.get_result_api(API + endpoint, method, payload)
        except ClientConnectionError as e:
            raise JsonRpcInternalError('could not connect to backend: ' + str(e))
        except JSONDecodeError as e:
            raise JsonRpcInternalError('solr did not respond with valid JSON', e.__dict__)
        except Exception as e:
            raise JsonRpcInternalError('something bad happened: ' + str(e), {'exception_type': str(type(e))})
        if 'error' in result:
            raise JsonRpcInternalError('solr responded with an error', result['error'])
        else:
            yield result
        yield {'responseHeader': {'status': 'finished'}}
        log.debug(f'FINISHED: {method}: {endpoint} {payload}')

    @command('send a request to solr', {
        'endpoint': 'the endpoint of the api: i.e. "/collections"',
        'method': 'one of [DELETE, PUT, GET, POST]',
        'payload': 'the parameters of the command, send an empty object for GET requests',
        'return': 'the result of the response'
    })
    async def pass_through_solr(self, endpoint: str, method: Method, payload: dict):
        print(f'{method}: {endpoint} {payload}')
        if isinstance(method, Method):
            method = method.value
        if method not in Method.__members__:
            raise JsonRpcInvalidParams(f'unsupported method: {method}, must be one of [DELETE, PUT, GET, POST]')
        yield {'responseHeader': {'status': 'accept'}}
        try:
            result = await self.get_result_solr(SOLR + endpoint, method, payload)
        except ClientConnectionError as e:
            raise JsonRpcInternalError('could not connect to backend: ' + str(e))
        except JSONDecodeError as e:
            raise JsonRpcInternalError('solr did not respond with valid JSON', e.__dict__)
        except Exception as e:
            raise JsonRpcInternalError('something bad happened: ' + str(e), {'exception_type': str(type(e))})
        if 'error' in result:
            raise JsonRpcInternalError('solr responded with an error', result['error'])
        else:
            yield result
        yield {'responseHeader': {'status': 'finished'}}
        log.debug(f'FINISHED: {method}: {endpoint} {payload}')

    @command('search a solr collection', {
        'collection': 'the collection you want to search in',
        'payload': 'the parameters of the search',
        'return': 'the result of the response'
    })
    async def select(self, collection: str, payload: dict):
        endpoint = f'/c/{collection}/select'
        async for res in self.pass_through(endpoint, Method.GET, payload):
            yield res

    @command('search a solr collection', {
        'collection': 'the collection you want to search in',
        'payload': 'the parameters of the search',
        'return': 'the result of the response'
    })
    async def get(self, collection: str, id: str):
        endpoint = f'/{collection}/get'
        async for res in self.pass_through_solr(endpoint, Method.GET, {'id': id}):
            yield res