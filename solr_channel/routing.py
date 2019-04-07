from django.conf.urls import url
from solr_channel import consumers
import logging
import json

log = logging.getLogger(__name__)
websocket_urlpatterns = [
    url(r'^ws/rpc/solr/$', consumers.JsonRpcSolrPassthrough)
]

for route in websocket_urlpatterns:
    if issubclass(route.callback, consumers.JsonRpcHandlerBase):
        log.error(f'{route.pattern}: {json.dumps(route.callback.commands.get(route.callback.__qualname__),indent=2)}')
        pass
