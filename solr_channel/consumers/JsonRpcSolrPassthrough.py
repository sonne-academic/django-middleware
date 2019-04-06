from django.utils import timezone
from django.core import exceptions as dex
from solr_channel.consumers.JsonRpcConsumer import JsonRpcResultResponse
from .JsonRpcHandlerBase import JsonRpcHandlerBase, command, Availability
from .JsonRpcExceptions import JsonRpcInvalidParams, JsonRpcInternalError, JsonRpcException
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientConnectionError
from json.decoder import JSONDecodeError
from enum import Enum
import logging
import random
import string
from django.conf import settings
from channels.db import database_sync_to_async
from solr_channel.models import Graph

API = f'{settings.SOLR_HOST}/api'
SOLR = f'{settings.SOLR_HOST}/solr'

log = logging.getLogger(__name__)
class Method(Enum):
    DELETE = "DELETE"
    PUT = "PUT"
    GET = "GET"
    POST = "POST"




class JsonRpcSolrPassthrough(JsonRpcHandlerBase):
    async def connect(self):
        self.groupname = ''.join(random.choice(string.ascii_letters) for i in range(12))
        conn = TCPConnector(limit=30)
        self.http = ClientSession(connector=conn)

        await self.channel_layer.group_add(group=self.groupname,channel=self.channel_name)
        return await super().connect()

    async def disconnect(self, code):
        await self.http.close()
        await self.channel_layer.group_discard(group=self.groupname,channel=self.channel_name)
        return await super().disconnect(code)

    async def get_result_api(self, endpoint: str, method: str, payload: dict) -> dict:
        log.debug(f'{method}: {endpoint} {payload}')
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
        log.debug(f'{method}: {endpoint} {params}')
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
            log.error(e)
            raise JsonRpcInternalError('something bad happened: ' + str(e), {'exception_type': str(type(e))})
        if 'error' in result:
            raise JsonRpcInternalError('solr responded with an error', result['error'])
        else:
            yield result
        yield {'responseHeader': {'status': 'finished'}}
        log.debug(f'FINISHED: {method}: {endpoint} {payload}')

    @command(Availability.PRODUCTION, {
        'collection': 'the collection you want to search in',
        'payload': 'the parameters of the search',
        'return': 'the result of the response'
    })
    async def select(self, collection: str, payload: dict, rqid: str):
        """
        search a solr collection
        """
        # endpoint = f'/c/{collection}/select'
        await self.channel_layer.group_send(self.groupname, {
            'type': 'group.select',
            'collection': collection,
            'payload': payload,
            'rqid': rqid
        })
        yield None
        # async for res in self.pass_through(endpoint, Method.GET, payload, rqid):
        #     yield res

    @command(Availability.PRODUCTION, {
        'collection': 'the collection you want to search in',
        'id': 'the document id'
    })
    async def get(self, collection: str, id: str, rqid: str):
        """
        search a solr collection
        """
        await self.channel_layer.group_send(self.groupname, {
            'type': 'group.get',
            'collection': collection,
            'id': id,
            'rqid': rqid
        })
        # async for res in self.pass_through_solr(endpoint, Method.GET, {'id': id}, rqid):
        #     yield res
        yield None

    @command(Availability.PRODUCTION, {
        'collection': 'the collection to search in',
        'author': 'the author to give positions for',
        'rows': 'the number of publications by this author'
    })
    async def author_position(self, collection: str, author: str, rows: int, rqid: str):
        """
        get the position of an author in their publications
        """
        await self.channel_layer.group_send(self.groupname, {
            'type': 'group.author_position',
            'collection': collection,
            'author': author,
            'rows': rows,
            'rqid': rqid
        })
        yield None

    @command(Availability.PRODUCTION, {
        'graph': 'the graph as string',
    })
    async def store_new_graph(self, graph: str, rqid: str):
        """
        store a graph in the database
        """
        await self.accept_command(rqid)
        new_id = await self.create_graph(graph)
        await self.send_response(JsonRpcResultResponse({'id': str(new_id)},rqid))
        await self.finished_command(rqid)
        yield None

    @database_sync_to_async
    def create_graph(self, graph: str):
        stored = Graph(graph_str=graph, ctime=timezone.now(), mtime=timezone.now())
        stored.save()
        return stored.id

    @command(Availability.PRODUCTION, {
        'graph_id': 'the uuid of a graph'
    })
    async def get_graph(self, graph_id: str, rqid: str):
        """
        get a graph from the database
        """
        await self.accept_command(rqid)
        graph = await self.get_graph_from_db(graph_id)
        graph_str = await self.decode_json(graph.graph_str)
        await self.send_response(JsonRpcResultResponse({'graph': graph_str},rqid))
        await self.finished_command(rqid)
        yield None

    @database_sync_to_async
    def get_graph_from_db(self, graph_id):
        try:
            return Graph.objects.get(id=graph_id)
        except dex.ObjectDoesNotExist:
            raise JsonRpcInvalidParams(f'no graph with id: {graph_id}')
        except dex.ValidationError as e:
            raise JsonRpcInvalidParams(str(e))

    @command(Availability.PRODUCTION,{
        'graph_id': 'id of graph to update',
        'data': 'the new value'
    })
    async def update_graph(self, graph_id: str, data: str, rqid):
        """
        update an existing graph
        """
        await self.accept_command(rqid)
        graph = await self.store_graph(graph_id, data)
        await self.send_response(JsonRpcResultResponse({'id': str(graph.id)},rqid))
        await self.finished_command(rqid)
        yield None

    @database_sync_to_async
    def store_graph(self, graph_id, data):
        try:
            graph = Graph.objects.get(id=graph_id)
            graph.graph_str = data
            graph.save()
            return graph
        except dex.ObjectDoesNotExist:
            raise JsonRpcInvalidParams(f'no graph with id: {graph_id}')
        except dex.ValidationError as e:
            raise JsonRpcInvalidParams(str(e))

    async def finished_command(self, request_id):
        msg = {'responseHeader': {'status': 'finished'}}
        response = JsonRpcResultResponse(msg, request_id)
        await self.send_response(response)

    async def accept_command(self, request_id):
        msg = {'responseHeader': {'status': 'accept'}}
        response = JsonRpcResultResponse(msg, request_id)
        await self.send_response(response)

    async def group_get(self, event):
        log.info(event)
        rqid = event['rqid']

        collection = event['collection']
        endpoint = f'/c/{collection}/get'
        try:
            async for res in self.pass_through(endpoint, Method.GET, {'params':{'id': event['id']}}, rqid):
                msg = JsonRpcResultResponse(res, rqid)
                await self.send_response(msg)
        except JsonRpcException as e:
            await self.send_error(e, rqid)
            return

    async def group_select(self, event):
        log.info(event)

        rqid = event['rqid']
        collection = event['collection']
        payload = event['payload']
        endpoint = f'/c/{collection}/select'
        # await self.accept_command(rqid)
        try:
            async for res in self.pass_through(endpoint, Method.GET, payload, rqid):
                msg = JsonRpcResultResponse(res, rqid)
                await self.send_response(msg)
        except JsonRpcException as e:
            await self.send_error(e, rqid)
            return
        #await self.finished_command(rqid)

    async def group_author_position(self, event):
        log.info(event)
        rqid = event['rqid']
        collection = event['collection']
        author = event['author']
        rows = event['rows']
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
        endpoint = f'/{collection}/stream'
        try:
            async for res in self.pass_through_solr(endpoint, Method.GET, params, rqid):
                msg = JsonRpcResultResponse(res, rqid)
                await self.send_response(msg)
        except JsonRpcException as e:
            await self.send_error(e, rqid)
            return
