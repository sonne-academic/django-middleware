from django.conf.urls import url
from solr_channel import consumers
websocket_urlpatterns = [
    url(r'^ws/rpc/solr/$', consumers.JsonRpcSolrPassthrough)
]