from .JsonRpcHandlerBase import JsonRpcHandlerBase, command
from .JsonRpcExceptions import JsonRpcInvalidParams, JsonRpcInternalError
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientConnectionError
from json.decoder import JSONDecodeError
from enum import Enum
import logging
import asyncio

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

    async def get_result(self, endpoint: str, method: str, payload: dict) -> dict:
        async with ClientSession() as sess:
            if "DELETE" == method:
                async with sess.delete('http://localhost:8983/api' + endpoint, json=payload) as response:
                    return await response.json()
            if "PUT" == method:
                async with sess.put('http://localhost:8983/api' + endpoint, json=payload) as response:
                    return await response.json()
            if "GET" == method:
                async with sess.get('http://localhost:8983/api' + endpoint, json=payload) as response:
                    return await response.json()
            if "POST" == method:
                async with sess.post('http://localhost:8983/api' + endpoint, json=payload) as response:
                    return await response.json()

    @command('send a command to solr', {
        'endpoint': 'the endpoint of the api: i.e. "/collections"',
        'method': 'one of [DELETE, PUT, GET, POST]',
        'payload': 'the parameters of the command, send an empty object for GET requests',
        'return': 'the result of the response'
    })
    async def pass_through(self, endpoint: str, method: Method, payload: dict):
        logging.debug(f'{method}: {endpoint} {payload}')
        if isinstance(method, Method):
            method = method.value
        if method not in Method.__members__:
            raise JsonRpcInvalidParams(f'unsupported method: {method}, must be one of [DELETE, PUT, GET, POST]')
        yield {'responseHeader': {'status': 'accept'}}
        try:
            result = await self.get_result(endpoint, method, payload)
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
        logging.debug(f'FINISHED: {method}: {endpoint} {payload}')
