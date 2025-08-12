from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.landing_page, name='landing_page'),
    path("quiz/<str:join_code>/<int:participant_id>/", views.participant_quiz, name="participant_quiz"),
    path("my-admin/<str:join_code>/", views.admin_dashboard, name="admin_dashboard"),
    
    # Session management
    path('create-session/', views.create_session, name='create_session'),
    path('session/<str:join_code>/results/', views.session_results, name='session_results'),

    # API endpoints for real-time functionality
    path("api/submit-answer/", views.api_submit_answer, name="submit_answer"),
    path("api/update-answer-points/", views.api_update_answer_points, name="update_answer_points"),
    path("api/send-question/", views.api_send_question, name="send_question"),

    # Data API endpoints
    path("api/live-answers/<str:session_code>/", views.api_live_answers, name="api_live_answers"),
    path("api/scores/<int:session_id>/", views.api_scores, name="api_scores"),
    path("api/session-status/<str:session_code>/", views.api_session_status, name="api_session_status"),
    path("api/questions/category/<int:category_id>/", views.api_get_questions_for_category, name="api_get_questions_for_category"),
    
    # Legacy endpoint (keeping for backward compatibility)
    path("get-questions-for-category/<int:category_id>/", views.api_get_questions_for_category, name="get_questions_for_category"),
]