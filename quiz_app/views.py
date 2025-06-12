# quiz_app/views.py
from django.shortcuts import render, get_object_or_404, redirect # redirect importieren
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

# Importiere die notwendigen Channels-Utilities
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import QuizSession, Question, Participant, ParticipantAnswer 
# QuizConsumer wird hier nicht mehr direkt für send_question_to_session benötigt
# from .consumers import QuizConsumer 

# --- NEU: Landing Page für die Code-Eingabe ---
def join_quiz_session(request):
    error_message = None
    if request.method == 'POST':
        join_code = request.POST.get('join_code')
        if join_code:
            try:
                # Versuche, die Session mit dem join_code zu finden
                session = QuizSession.objects.get(join_code=join_code)
                # Wenn gefunden, leite zur Teilnehmerseite weiter
                # Verwende die UUID für die Weiterleitung zur participant_view
                return redirect('participant_view', session_code=str(session.session_code))
            except QuizSession.DoesNotExist:
                error_message = "Ungültiger Session-Code. Bitte versuchen Sie es erneut."
        else:
            error_message = "Bitte geben Sie einen Session-Code ein."

    return render(request, 'quiz_app/join_session.html', {'error_message': error_message})
# --- ENDE NEU ---


def participant_view(request, session_code):
    session = get_object_or_404(QuizSession, session_code=session_code)
    
    participant = None
    participant_id = request.session.get('participant_id')
    if participant_id:
        participant = Participant.objects.filter(id=participant_id, session=session).first()
    
    if not participant:
        participant_name = f"Gast_{Participant.objects.filter(session=session).count() + 1}"
        participant = Participant.objects.create(session=session, name=participant_name)
        request.session['participant_id'] = participant.id

    current_question = session.current_question if hasattr(session, 'current_question') else None
    
    context = {
        'session': session,
        'participant': participant,
        'current_question': current_question,
        'answers': current_question.get_all_answers() if current_question else [], # Wichtig für das Template
    }
    return render(request, 'quiz_app/participant_quiz.html', context)


@csrf_exempt 
def send_question(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        session_code = data.get('session_code')
        question_id = data.get('question_id')

        try:
            session = QuizSession.objects.get(session_code=session_code)
            question = Question.objects.get(id=question_id)

            session.current_question = question
            session.save()

            if not session.is_active:
                session.is_active = True
                session.save()

            channel_layer = get_channel_layer()
            if channel_layer is None:
                print("Fehler: Channels Layer ist nicht verfügbar im send_question View.")
                return JsonResponse({"status": "error", "message": "Channels Layer ist nicht verfügbar."}, status=500)

            message_data = {
                'type': 'new_question',
                'question_id': question.id,
                'question_text': question.text,
                'answers': question.get_all_answers(),
            }

            async_to_sync(channel_layer.group_send)(
                f'quiz_{session_code}',
                {
                    'type': 'quiz_message', 
                    'message': message_data
                }
            )
            print(f"Frage {question_id} erfolgreich an Session {session_code} via WebSocket gesendet.")
            return JsonResponse({"status": "success", "message": "Frage gesendet!"})

        except QuizSession.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Session nicht gefunden."}, status=404)
        except Question.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Frage nicht gefunden."}, status=404)
        except Exception as e:
            print(f"Ein unerwarteter Fehler im send_question View: {str(e)}")
            return JsonResponse({"status": "error", "message": f"Fehler beim Senden der Frage: {str(e)}"}, status=500)
    return JsonResponse({"status": "error", "message": "Ungültige Request-Methode."}, status=405)


@csrf_exempt 
def submit_answer_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question_id = data.get('question_id')
            chosen_answer_text = data.get('chosen_answer_text') 

            participant = None
            participant_id = request.session.get('participant_id')
            if participant_id:
                participant = get_object_or_404(Participant, id=participant_id)
            else:
                return JsonResponse({"status": "error", "message": "Teilnehmer nicht identifiziert. Bitte Seite neu laden."}, status=403)
            
            question = get_object_or_404(Question, id=question_id)
            
            is_correct = (chosen_answer_text == question.correct_answer)

            ParticipantAnswer.objects.update_or_create(
                participant=participant,
                question=question,
                defaults={
                    'chosen_answer': chosen_answer_text,
                    'is_correct': is_correct
                }
            )

            return JsonResponse({"status": "success", "message": "Antwort erfolgreich gespeichert."})
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Ungültiger JSON-Request."}, status=400)
        except (Question.DoesNotExist, Participant.DoesNotExist):
            return JsonResponse({"status": "error", "message": "Fehlende Daten (Frage oder Teilnehmer nicht gefunden)."}, status=404)
        except Exception as e:
            print(f"Serverfehler: {str(e)}", status=500)
            return JsonResponse({"status": "error", "message": f"Serverfehler: {str(e)}"}, status=500)
    return JsonResponse({"status": "error", "message": "Methode nicht erlaubt."}, status=405)


from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def admin_dashboard(request, session_code):
    session = get_object_or_404(QuizSession, session_code=session_code)
    questions = Question.objects.all()
    current_answers = ParticipantAnswer.objects.filter(
        question=session.current_question,
        participant__session=session
    ).select_related('participant')

    context = {
        'session': session,
        'questions': questions,
        'current_answers': current_answers,
    }
    return render(request, 'quiz_app/admin_dashboard.html', context)