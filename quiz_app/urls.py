from django.urls import path
from . import views

urlpatterns = [
	# admin dashboard
	path('send-question/', views.send_question, name='send_question'),
	path('session/<str:join_code>/current-question/', views.current_question, name='show_current_question'),
	path('admin-dashboard/<str:join_code>/', views.admin_dashboard, name='admin_dashboard'),

	# users
	path('', views.landing_page, name='Landing page'),

	path("admin/<str:join_code>/", views.admin_dashboard, name="admin_dashboard"),
    path("quiz/<str:join_code>/<int:participant_id>/", views.participant_quiz, name="participant_quiz"),

    # API routes
    path("api/live-answers/<str:session_code>/", views.api_live_answers),
    path("api/scores/<int:session_id>/", views.api_scores),
    path("get-questions-for-category/<int:category_id>/", views.api_get_questions_for_category),

    path("submit-answer/", views.api_submit_answer, name="submit_answer"),
    path("update_answer_points/", views.api_update_answer_points, name="update_answer_points"),
    
]
