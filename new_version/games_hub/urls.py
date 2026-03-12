from django.urls import path
from . import views

app_name = 'games_hub'

urlpatterns = [
    path('create/', views.create_session, name='create_session'),
    path('lobby/<str:session_code>/', views.lobby, name='lobby'),
    path('monitor/<str:session_code>/', views.monitor, name='monitor'),
    path('session/<str:session_code>/leaderboard/', views.session_leaderboard, name='session_leaderboard'),
    # API endpoints
    path('api/session/<str:session_code>/leaderboard/', views.session_leaderboard_api, name='session_leaderboard_api'),
    path('api/session/<str:session_code>/add-step/', views.add_step_to_session, name='add_step_to_session'),
    path('api/participant/score/', views.set_hub_participant_score, name='set_hub_participant_score'),
]
