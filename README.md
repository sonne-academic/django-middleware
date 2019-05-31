This is the django/daphne webserver for sonne.0ds.de

# deployment

To deploy, we use nginx, see the files in the `nginx` folder for our configuration.
The service is managed through systemd, the configuration is in the `systemd` folder.


## manual installation

Our configuration and deployment uses the following folders:

  - `/srv/http/sonne` contains the django application (everything within the `src` folder).
  - `/srv/http/static` contains the compiled (frontend)[https://github.com/sonne-academic/vue-frontend].

As your `http` user (you do not run this as root, right?), place the contents of the src folder into `/srv/http/sonne`.
Then run `pip install --user -r requirements.txt` to install all necessary dependencies.

Currently, the server will run in production mode, if the hostname is `sonne`.
If that is not to your liking, change the hostname in the settings.py, so the server is not run in debug mode (because that is dangerous)!

```python
python manage.py migrate
python manage.py collectstatic --no-input
```

will prepare the database and place all files where they are expected to be.

Once this completed without error, copy the `daphne.service` to `/etc/systemd/system`, and the content of the nginx directory to `/etc/nginx`.
Use `systemctl enable --now daphne` to start the server and autostart it on boot.

## CI/CD

We use a gitlab-runner on the host that is running the web server, for details see the `.gitlab-ci` and the (gitlab-runner documentation)[https://about.gitlab.com/product/continuous-integration/#gitlab-runner].
If you deploy to the same paths as we do, this should take care of everything on the python side.
You'll still have to configure nginx and systemd to serve the connection.

# development

in the source directory, create a new venv with `python -m venv venv`, and activate the environment with `source ./venv/bin/activate`.
then install all requirements with `pip install -r requirements.txt`.
If you don't want to use a venv, you can use `pip install --user -r requirements.txt` instead.

run the server with `./manage.py runserver` 

## project structure

`channels_zeromq` contains the channel layer for django-channels, this is a very basic pub-sub implementation and can be used to deliver a message to several connected clients.
It can also be used to do take some load off of the django-server in case the app has many users, then the channel layer needs to be configured to use another host, and the pub-sub server needs to be run (and implemented!) there.

`solr_channel` is the *logic* part, the `consumers` subfolder is the most interesting, the rest is just the basic django stuff.
`JsonRpcHandlerBase` is subclassed by `JsonRpcSolrPassthrough`, which in turn implements the various JSON-RPC commands via the `@chn_command` decorator.

### define new web socket endpoint

when you want to add an endpoint, create a new class that inherits from `JsonRpcHandlerBase` and use the `@chn_command` to define new commands.

Then add it to the `solr_channel/routing.py` patterns, to register it with django.

```python
@chn_command(Availability.PRODUCTION, {
    'collection': 'the collection you want to search in',
    'id': 'the document id'
})
async def solr_get(self, event: SolrGet) -> None:
```

`SolrGet` is a dataclass that is used for generating the documentation and validation of the client-sent parameters.

```python
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
They are populated automatically and are important within a command function.

Once you're done with the function, return the result; the base class will deliver the response with this payload.
The base class will also handle any exception that is raised and wrap it into an error, that is sent to the client.

If you don't like the base handler and want to do everything manually, refert to the [channels documentation](https://channels.readthedocs.io/en/latest/), in detail the [consumers](https://channels.readthedocs.io/en/latest/topics/consumers.html) section.
