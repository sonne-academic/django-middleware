from django.db import models
import uuid

class Graph(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    graph_str = models.TextField()
    ctime = models.DateTimeField('creation time')
    mtime = models.DateTimeField('modification time')