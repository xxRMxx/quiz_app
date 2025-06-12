# quiz_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # NEU: Landing Page für die Code-Eingabe
    path('', views.join_quiz_session, name='join_quiz_session'), # Dies ist die Startseite

    path('quiz/<uuid:session_code>/', views.participant_view, name='participant_view'),
    path('send-question/', views.send_question, name='send_question'), 
    path('submit-answer/', views.submit_answer_view, name='submit_answer'),
    path('admin-dashboard/<uuid:session_code>/', views.admin_dashboard, name='admin_dashboard'),
]