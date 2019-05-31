This is the django/daphne webserver for sonne.0ds.de

# development

in the source directory, create a new venv with `python -m venv venv`, and activate the environment with `source ./venv/bin/activate`.
then install all requirements with `pip install -e requirements.txt`.

## project structure

`channels_zeromq` contains the channel layer for django-channels, this is a very basic pub-sub implementation and can be used to deliver a message to several connected clients.
It can also be used to do take some load off of the django-server in case the app has many users, then the channel layer needs to be configured to use another host, and the pub-sub server needs to be run (and implemented!) there.

`solr_channel` is the *logic* part, the `consumers` subfolder is the most interesting, the rest is just the basic django stuff.
`JsonRpcHandlerBase` is subclassed by `JsonRpcSolrPassthrough`, which in turn implements the various JSON-RPC commands via the `@chn_command` decorator.

### define new web socket endpoint

when you want to add an endpoint, create a new class that inherits from `JsonRpcHandlerBase` and use the `@chn_command` to define new commands.

Then add it to the `solr_channel/routing.py` patterns, to register it with django.

```python3
@chn_command(Availability.PRODUCTION, {
    'collection': 'the collection you want to search in',
    'id': 'the document id'
})
async def solr_get(self, event: SolrGet) -> None:
```

`SolrGet` is a dataclass that is used for generating the documentation and validation of the client-sent parameters.

```python3
@dataclass
class SolrBaseParams:
    rqid: str
    type: str

@dataclass
class SolrGet(SolrBaseParams):
    collection: str
    id: str
```

`rqid` and `type` are necessary for the system to know which request we serve and which function is called.


# deployment


