import logging
import random
import string
from dataclasses import dataclass
from enum import Enum
from json.decoder import JSONDecodeError
from typing import List

from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientConnectionError, ClientConnectorError
from channels.db import database_sync_to_async
from django.conf import settings
from django.core import exceptions as dex
from django.utils import timezone

from solr_channel.consumers.JsonRpcConsumer import JsonRpcResultResponse
from solr_channel.models import Graph
from .JsonRpcExceptions import JsonRpcInvalidParams, JsonRpcInternalError, JsonRpcException
from .JsonRpcHandlerBase import JsonRpcHandlerBase, command, Availability, chn_command

API = f'{settings.SOLR_HOST}/api'
SOLR = f'{settings.SOLR_HOST}/solr'

log = logging.getLogger(__name__)


@dataclass
class AuthorPosition:
    senior_count: int
    count: int
    position: int


@dataclass
class SolrBaseParams:
    rqid: str
    type: str


@dataclass
class SolrGet(SolrBaseParams):
    collection: str
    id: str

@dataclass
class SolrAuthorPosition(SolrBaseParams):
    collection: str
    author: str
    rows: int


@dataclass
class SolrSelect(SolrBaseParams):
    collection: str
    payload: dict

class Method(Enum):
    DELETE = "DELETE"
    PUT = "PUT"
    GET = "GET"
    POST = "POST"



@database_sync_to_async
def create_graph(graph: str):
    stored = Graph(graph_str=graph, ctime=timezone.now(), mtime=timezone.now())
    stored.save()
    return stored.id


@database_sync_to_async
def get_graph_from_db(graph_id):
    try:
        return Graph.objects.get(id=graph_id)
    except dex.ObjectDoesNotExist:
        raise JsonRpcInvalidParams(f'no graph with id: {graph_id}')
    except dex.ValidationError as e:
        raise JsonRpcInvalidParams(str(e))


@database_sync_to_async
def store_graph(graph_id, data):
    try:
        graph = Graph.objects.get(id=graph_id)
        graph.graph_str = data
        graph.save()
        return graph
    except dex.ObjectDoesNotExist:
        raise JsonRpcInvalidParams(f'no graph with id: {graph_id}')
    except dex.ValidationError as e:
        raise JsonRpcInvalidParams(str(e))


class JsonRpcSolrPassthrough(JsonRpcHandlerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_name = ''
        self.http: ClientSession = None

    async def connect(self):
        self.group_name = ''.join(random.choice(string.ascii_letters) for _ in range(12))
        conn = TCPConnector(limit=2)
        self.http = ClientSession(connector=conn)
        await self.channel_layer.group_add(group=self.group_name, channel=self.channel_name)
        return await super().connect()

    async def disconnect(self, code):
        await self.http.close()
        await self.channel_layer.group_discard(group=self.group_name, channel=self.channel_name)
        self.group_name = ''
        return await super().disconnect(code)

    def _method(self, m: Method):
        if Method.GET == m:
            return self.http.get
        if Method.POST == m:
            return self.http.post
        if Method.DELETE == m:
            return self.http.delete
        if Method.PUT == m:
            return self.http.put

    async def solr_http(self, endpoint: str, method: Method, json=None, params=None):
        async with self._method(method)(endpoint, json=json, params=params) as response:
            log.info(response.request_info)
            result =  await response.json()
            if 'error' in result:
                raise JsonRpcInternalError('solr responded with an error', result['error'])
            else:
                return result

    async def get_result_api(self, endpoint: str, method: Method, payload: dict) -> dict:
        log.info(f'{method}: {endpoint} {payload}')
        async with self._method(method)(endpoint, json=payload) as response:
            return await response.json()

    async def get_result_solr(self, endpoint: str, method: Method, params: dict) -> dict:
        log.debug(f'{method}: {endpoint} {params}')
        async with self._method(method)(endpoint, params=params) as response:
            return await response.json()

    async def handle_exception(self, e: Exception, msg_id: str):
        if type(e) is ClientConnectionError:
            e = JsonRpcInternalError('could not connect to backend: ' + str(e))
        elif type(e) is ClientConnectorError:
            e = JsonRpcInternalError('could not connect to backend: ' + str(e))
        elif type(e) is JSONDecodeError:
            e = JsonRpcInternalError('solr did not respond with valid JSON', e.__dict__)

        await super().handle_exception(e,msg_id)

    @command(Availability.DEBUG_ONLY, {
        'endpoint': 'the endpoint of the api: i.e. "/collections"',
        'method': 'one of [DELETE, PUT, GET, POST]',
        'payload': 'the parameters of the command, send an empty object for GET requests',
        'return': 'the result of the response'
    })
    async def pass_through(self, endpoint: str, method: Method, payload: dict, rqid: str):
        """
        send a command to the solr api
        """
        log.debug(f'{method}: {endpoint} {payload}')
        if isinstance(method, str):
            try:
                method = Method(method)
            except ValueError:
                raise JsonRpcInvalidParams(f'unsupported method: {method}, must be one of [DELETE, PUT, GET, POST]')
        try:
            result = await self.get_result_api(API + endpoint, method, payload)
        except Exception as e:
            return await self.handle_exception(e, rqid)

        if 'error' in result:
            raise JsonRpcInternalError('solr responded with an error', result['error'])
        else:
            await self.send_response(JsonRpcResultResponse(result,rqid))

    @command(Availability.DEBUG_ONLY, {
        'endpoint': 'the endpoint of the api: i.e. "/collections"',
        'method': 'one of [DELETE, PUT, GET, POST]',
        'payload': 'the parameters of the command, send an empty object for GET requests',
        'return': 'the result of the response'
    })
    async def pass_through_solr(self, endpoint: str, method: Method, payload: dict, rqid: str):
        """
        send a request to solr
        """
        log.debug(f'{method}: {endpoint} {payload}')
        if isinstance(method, str):
            try:
                method = Method(method)
            except ValueError:
                raise JsonRpcInvalidParams(f'unsupported method: {method}, must be one of [DELETE, PUT, GET, POST]')

        try:
            result = await self.get_result_solr(SOLR + endpoint, method, payload)
        except Exception as e:
            return await self.handle_exception(e, rqid)
        if 'error' in result:
            raise JsonRpcInternalError('solr responded with an error', result['error'])
        else:
            await self.send_response(JsonRpcResultResponse(result,rqid))

    @command(Availability.PRODUCTION, {
        'graph': 'the graph as string',
    })
    async def store_new_graph(self, graph: str, rqid: str):
        """
        store a graph in the database
        """
        new_id = await create_graph(graph)
        await self.send_response(JsonRpcResultResponse({'uuid': str(new_id)}, rqid))

    @command(Availability.PRODUCTION, {
        'graph_id': 'the uuid of a graph'
    })
    async def get_graph(self, graph_id: str, rqid: str):
        """
        get a graph from the database
        """
        graph = await get_graph_from_db(graph_id)
        graph_str = await self.decode_json(graph.graph_str)
        await self.send_response(JsonRpcResultResponse({'graph': graph_str}, rqid))

    @command(Availability.PRODUCTION, {
        'graph_id': 'id of graph to update',
        'data': 'the new value'
    })
    async def update_graph(self, graph_id: str, data: str, rqid):
        """
        update an existing graph
        """
        graph = await store_graph(graph_id, data)
        await self.send_response(JsonRpcResultResponse({'uuid': str(graph.id)}, rqid))

    @chn_command(Availability.PRODUCTION, {
        'collection': 'the collection you want to search in',
        'payload': 'the parameters of the search',
        'return': 'the result of the response'
    })
    async def solr_select(self, ev: SolrSelect) -> None:
        collection = ev.collection
        payload = ev.payload
        endpoint = f'{API}/c/{collection}/select'
        result = await self.solr_http(endpoint,Method.GET,json=payload)
        log.info(result)
        return result

    @chn_command(Availability.PRODUCTION, {
        'collection': 'the collection to search in',
        'author': 'the author to give positions for',
        'rows': 'the number of publications by this author'
    })
    async def solr_author_position(self, event: SolrAuthorPosition) -> List[AuthorPosition]:
        """
        Calculate the occuring positions of an author.
        """
        collection = event.collection
        author = event.author
        rows = event.rows
        expr = f'''
        select(
            rollup(
                sort(
                    select(
                        search(
                        {collection},
                        q=author:"{author}",
                        fl="author, author_count, id",
                        sort="id desc",
                        qt=/select,
                        rows={rows}
                        )
                    , add(1,indexOf(author, "{author}")) as position
                    , if(eq(author_count,position), 1,0) as is_last
                    )
                , by="position asc"
                )
            , over="position", count(*), sum(is_last)
            )
        , count(*) as count
        , position
        , sum(is_last) as senior_count
        )'''
        params = {'expr': expr}
        endpoint = f'{SOLR}/{collection}/stream'
        result = await self.solr_http(endpoint, Method.POST, params=params)
        if 'result-set' not in result:
            pass
        result = result['result-set']
        if 'docs' not in result:
            pass
        r: list = result['docs']
        last = r.pop()
        log.info(r)
        log.info(last)
        return r
        # return await self.send_result(result, event.rqid)

    @chn_command(Availability.PRODUCTION, {
        'collection': 'the collection you want to search in',
        'id': 'the document id'
    })
    async def solr_get(self, event: SolrGet) -> None:
        collection = event.collection
        url = f'{API}/c/{collection}/get'
        return await self.solr_http(url, Method.GET, json={'params': {'id': event.id}})
