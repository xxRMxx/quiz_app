from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/quiz/(?P<session_code>[0-9a-f-]+)/$', consumers.QuizConsumer.as_asgi()),
]
