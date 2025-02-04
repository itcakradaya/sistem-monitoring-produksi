from django.urls import re_path
from .consumers import ProsesProduksiConsumer

websocket_urlpatterns = [
    re_path(r"ws/monitoring/(?P<ruangan_nama>\w+)/$", ProsesProduksiConsumer.as_asgi()),
]
