import json
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Count, Avg, Sum
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import (
    Category,
    Question,
    Session,
    Participant,
    ParticipantAnswer,
    SessionQuestion
)


def landing_page(request):
    """Landing page for participants to join quiz sessions"""
    if request.method == "POST":
        participant_name = request.POST.get("participant_name")
        join_code = request.POST.get("join_code")
        
        if not participant_name or not join_code:
            error_message = "Bitte geben Sie sowohl Namen als auch Session-Code ein."
            return render(request, "quiz_app/landing_page.html", {"error_message": error_message})
        
        try:
            session = Session.objects.get(join_code=join_code)
        except Session.DoesNotExist:
            error_message = "Ungültiger Session-Code. Bitte überprüfen Sie den Code."
            return render(request, "quiz_app/landing_page.html", {"error_message": error_message})
        
        # Check if session allows late joins
        if session.status == 'finished':
            error_message = "Diese Session ist bereits beendet."
            return render(request, "quiz_app/landing_page.html", {"error_message": error_message})
        
        if session.status == 'active' and not session.allow_late_joins:
            error_message = "Diese Session läuft bereits und erlaubt keine neuen Teilnehmer."
            return render(request, "quiz_app/landing_page.html", {"error_message": error_message})
        
        # Check if participant name already exists in this session
        if Participant.objects.filter(session=session, name=participant_name).exists():
            error_message = f"Der Name '{participant_name}' ist bereits in dieser Session vergeben."
            return render(request, "quiz_app/landing_page.html", {"error_message": error_message})
        
        # Create new participant
        participant = Participant.objects.create(
            name=participant_name, 
            session=session,
            is_connected=True
        )

        # Notify admin via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'quiz_{session.session_code}',
            {
                'type': 'participant_joined',
                'participant': {
                    'id': participant.id,
                    'name': participant.name,
                    'points': participant.points
                }
            }
        )

        return redirect("participant_quiz", join_code=join_code, participant_id=participant.id)

    else:
        return render(request, "quiz_app/landing_page.html")


def participant_quiz(request, join_code, participant_id):
    """Quiz interface for participants"""
    session = get_object_or_404(Session, join_code=join_code)
    participant = get_object_or_404(Participant, id=participant_id, session=session)

    # Update participant's last seen
    participant.last_seen = timezone.now()
    participant.is_connected = True
    participant.save(update_fields=['last_seen', 'is_connected'])

    # Get current question and answers
    current_question = session.current_question
    answers = []
    user_answer = None
    
    if current_question:
        answers = current_question.get_all_answers()
        # Check if user already answered this question
        try:
            user_answer = ParticipantAnswer.objects.get(
                participant=participant,
                question=current_question
            )
        except ParticipantAnswer.DoesNotExist:
            user_answer = None

    # Get participant's current rank
    rank = Participant.objects.filter(
        session=session,
        points__gt=participant.points
    ).count() + 1

    context = {
        "session": session,
        "participant": participant,
        "current_question": current_question,
        "answers": answers,
        "user_answer": user_answer,
        "rank": rank,
        "total_participants": session.participants.count(),
    }

    return render(request, "quiz_app/participant_quiz.html", context)


def admin_dashboard(request, join_code):
    """Admin dashboard for managing quiz sessions"""
    session = get_object_or_404(Session, join_code=join_code)
    categories = Category.objects.all()
    questions = Question.objects.select_related('category').all()
    participants = session.participants.all().order_by('-points', 'name')

    # Get current question answers if exists
    current_answers = []
    if session.current_question:
        current_answers = ParticipantAnswer.objects.filter(
            question=session.current_question,
            participant__session=session
        ).select_related('participant').order_by('-submitted_at')

    # Session statistics
    stats = {
        'total_participants': participants.count(),
        'connected_participants': participants.filter(is_connected=True).count(),
        'total_questions_asked': session.current_question_number,
        'average_score': participants.aggregate(avg_score=Avg('points'))['avg_score'] or 0,
    }

    context = {
        "session": session,
        "categories": categories,
        "questions": questions,
        "current_answers": current_answers,
        "participants": participants,
        "stats": stats,
    }

    return render(request, "quiz_app/admin_dashboard.html", context)


@csrf_exempt
@require_POST
def api_submit_answer(request):
    """API endpoint for participants to submit answers"""
    try:
        data = json.loads(request.body)
        question_id = data.get("question_id")
        chosen_answer_text = data.get("chosen_answer_text")
        participant_id = data.get("participant_id")
        time_taken = data.get("time_taken")

        if not all([question_id, chosen_answer_text, participant_id]):
            return JsonResponse({
                "status": "error", 
                "message": "Fehlende Parameter."
            }, status=400)

        participant = get_object_or_404(Participant, id=participant_id)
        question = get_object_or_404(Question, id=question_id)

        # Check if answer already exists
        existing_answer = ParticipantAnswer.objects.filter(
            participant=participant,
            question=question
        ).first()

        if existing_answer:
            return JsonResponse({
                "status": "error", 
                "message": "Antwort bereits abgegeben."
            })

        # Create new answer
        answer = ParticipantAnswer.objects.create(
            participant=participant,
            question=question,
            chosen_answer=chosen_answer_text,
            time_taken=time_taken
        )

        # Notify admin via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'quiz_{participant.session.session_code}',
            {
                'type': 'participant_answered',
                'answer': {
                    'id': answer.id,
                    'participant_id': participant.id,
                    'participant_name': participant.name,
                    'chosen_answer': chosen_answer_text,
                    'is_correct': answer.is_correct,
                    'points_awarded': answer.points_awarded,
                    'time_taken': time_taken
                }
            }
        )

        return JsonResponse({
            "status": "success", 
            "message": "Antwort gespeichert!",
            "is_correct": answer.is_correct,
            "points_awarded": answer.points_awarded,
            "total_points": participant.points
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error", 
            "message": "Ungültige JSON-Daten."
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error", 
            "message": f"Fehler: {str(e)}"
        }, status=500)


@csrf_exempt
@require_POST
def api_update_answer_points(request):
    """API endpoint for admins to update answer points"""
    try:
        data = json.loads(request.body)
        answer_id = data.get("answer_id")
        new_points = int(data.get("new_points", 0))

        answer = get_object_or_404(ParticipantAnswer, id=answer_id)
        answer.points_awarded = new_points
        answer.save()

        # Notify all clients via WebSocket
        channel_layer = get_channel_layer()
        leaderboard = list(answer.participant.session.get_leaderboard().values(
            'id', 'name', 'points', 'is_connected'
        ))
        
        async_to_sync(channel_layer.group_send)(
            f'quiz_{answer.participant.session.session_code}',
            {
                'type': 'leaderboard_updated',
                'leaderboard': leaderboard
            }
        )

        return JsonResponse({
            "status": "success", 
            "new_points": answer.points_awarded,
            "participant_total": answer.participant.points
        })

    except (ValueError, TypeError):
        return JsonResponse({
            "status": "error", 
            "message": "Ungültige Punktzahl."
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error", 
            "message": f"Fehler: {str(e)}"
        }, status=500)


def api_get_questions_for_category(request, category_id):
    """API endpoint to get questions for a specific category"""
    questions = Question.objects.filter(category_id=category_id).values(
        "id", "question_text", "difficulty", "points", "time_limit"
    )
    return JsonResponse({"questions": list(questions)})


def api_live_answers(request, session_code):
    """API endpoint to get live answers for current question"""
    try:
        session = Session.objects.get(session_code=session_code)
        current_question = session.current_question
        
        if not current_question:
            return JsonResponse({"answers": []})

        answers = ParticipantAnswer.objects.filter(
            question=current_question,
            participant__session=session
        ).select_related('participant').order_by('-submitted_at')

        answers_data = []
        for answer in answers:
            answers_data.append({
                "id": answer.id,
                "participant_id": answer.participant.id,
                "name": answer.participant.name,
                "answer": answer.chosen_answer,
                "is_correct": answer.is_correct,
                "points": answer.points_awarded,
                "time_taken": answer.time_taken,
                "submitted_at": answer.submitted_at.isoformat()
            })

        return JsonResponse({"answers": answers_data})
        
    except Session.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)


def api_scores(request, session_id):
    """API endpoint to get participant scores"""
    try:
        session = Session.objects.get(id=session_id)
        participants = session.get_leaderboard()
        
        scores_data = []
        for participant in participants:
            scores_data.append({
                "id": participant.id,
                "name": participant.name,
                "points": participant.points,
                "is_connected": participant.is_connected,
                "answer_count": participant.answers.count(),
                "correct_answers": participant.answers.filter(is_correct=True).count()
            })

        return JsonResponse({"scores": scores_data})
        
    except Session.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)


def api_session_status(request, session_code):
    """API endpoint to get session status"""
    try:
        session = Session.objects.get(session_code=session_code)
        
        current_question_data = None
        if session.current_question:
            current_question_data = {
                "id": session.current_question.id,
                "text": session.current_question.question_text,
                "category": session.current_question.category.name,
                "number": session.current_question_number,
                "answers": session.current_question.get_all_answers() if session.status == 'active' else [],
                "time_limit": session.current_question.time_limit,
                "points": session.current_question.points
            }

        return JsonResponse({
            "session": {
                "id": session.id,
                "name": session.name,
                "status": session.status,
                "join_code": session.join_code,
                "current_question": current_question_data,
                "show_answers": session.show_answers,
                "show_leaderboard": session.show_leaderboard,
                "participant_count": session.participants.count()
            }
        })
        
    except Session.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)


@csrf_exempt
@require_POST
def api_send_question(request):
    """API endpoint for admin to send a question (triggers WebSocket)"""
    try:
        data = json.loads(request.body)
        session_code = data.get("session_code")
        question_id = data.get("question_id")

        session = get_object_or_404(Session, session_code=session_code)
        question = get_object_or_404(Question, id=question_id)

        # Update session
        session.current_question = question
        session.current_question_number += 1
        session.question_start_time = timezone.now()
        session.show_answers = False
        session.save()

        # Remove old answers for this question to start fresh
        ParticipantAnswer.objects.filter(
            question=question, 
            participant__session=session
        ).delete()

        # Send via WebSocket (this will be handled by the consumer)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'quiz_{session.session_code}',
            {
                'type': 'new_question',
                'question': {
                    'id': question.id,
                    'text': question.question_text,
                    'category': question.category.name,
                    'answers': question.get_all_answers(),
                    'time_limit': question.time_limit,
                    'points': question.points,
                    'number': session.current_question_number
                }
            }
        )

        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# Helper functions for session management
def create_session(request):
    """Create a new quiz session"""
    if request.method == 'POST':
        name = request.POST.get('name', 'Quiz Session')
        selected_categories = request.POST.getlist('categories')
        
        session = Session.objects.create(name=name)
        
        # Add questions from selected categories
        if selected_categories:
            questions = Question.objects.filter(category_id__in=selected_categories)
            for i, question in enumerate(questions, 1):
                SessionQuestion.objects.create(
                    session=session,
                    question=question,
                    order=i
                )
            session.total_questions = questions.count()
            session.save()
        
        messages.success(request, f'Session "{name}" created with join code: {session.join_code}')
        return redirect('admin_dashboard', join_code=session.join_code)
    
    categories = Category.objects.all()
    return render(request, 'quiz_app/create_session.html', {'categories': categories})


def session_results(request, join_code):
    """Display session results"""
    session = get_object_or_404(Session, join_code=join_code)
    participants = session.get_leaderboard()
    
    # Get question-by-question results
    questions_asked = Question.objects.filter(
        current_for_sessions=session
    ).distinct()
    
    results_data = []
    for question in questions_asked:
        answers = ParticipantAnswer.objects.filter(
            question=question,
            participant__session=session
        ).select_related('participant')
        
        correct_count = answers.filter(is_correct=True).count()
        total_count = answers.count()
        
        results_data.append({
            'question': question,
            'answers': answers,
            'correct_count': correct_count,
            'total_count': total_count,
            'accuracy': (correct_count / total_count * 100) if total_count > 0 else 0
        })
    
    context = {
        'session': session,
        'participants': participants,
        'results_data': results_data,
    }
    
    return render(request, 'quiz_app/session_results.html', context)