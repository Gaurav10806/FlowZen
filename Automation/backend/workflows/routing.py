"""
WebSocket URL routing for workflows app.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/execution/(?P<execution_id>[0-9a-f-]+)/$", consumers.ExecutionLogConsumer.as_asgi()),
]

