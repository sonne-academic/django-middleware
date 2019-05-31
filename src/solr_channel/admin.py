from django.contrib import admin
from .models import Graph


class GraphAdmin(admin.ModelAdmin):
    list_display = ['id', 'ctime', 'mtime']
    ordering = ['-mtime']

admin.site.register(Graph, GraphAdmin)