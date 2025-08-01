import json
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import (
	Category,
	Question,
	Session,
	Participant,
	ParticipantAnswer,
)


def landing_page(request):
	
	if request.method == "POST":
		participant_name = request.POST.get("participant_name")
		join_code = request.POST.get("join_code")
		
		try:
			session = Session.objects.get(join_code=join_code)
		except Session.DoesNotExist:
			error_message = "Ungültiger Session-Code."
			return render(request, "quiz_app/landing_page.html", {"error_message": error_message})
		
		# create a new participant
		participant = Participant.objects.create(name=participant_name, session=session)

		return redirect("participant_quiz", join_code=join_code, participant_id=participant.id)

	else:
		return render(request, "quiz_app/landing_page.html")


def participant_quiz(request, join_code, participant_id):
	session = get_object_or_404(Session, join_code=join_code)
	participant = get_object_or_404(Participant, id=participant_id, session=session)

	current_question = session.current_question
	answers = []
	current_category = None
	if current_question:
		answers = [current_question.correct_answer] + current_question.wrong_answers
		import random

		random.shuffle(answers)
		current_category = current_question.category

	return render(
		request,
		"quiz_app/participant_quiz.html",
		{
			"session": session,
			"participant": participant,
			"current_question": current_question,
			"answers": answers,
			"current_category": current_category,
		},
	)


def admin_dashboard(request, join_code):
	session = get_object_or_404(Session, join_code=join_code)
	categories = Category.objects.all()
	questions = Question.objects.all()
	participants = Participant.objects.all().filter(session=session)

	current_answers = (
		ParticipantAnswer.objects.filter(question=session.current_question).select_related("participant")
		if session.current_question
		else []
	)

	return render(
		request,
		"quiz_app/admin_dashboard.html",
		{
			"session": session,
			"categories": categories,
			"questions": questions,
			"current_answers": current_answers,
			"participants": participants,
		},
	)





def current_question(request, join_code):
    session = get_object_or_404(Session, join_code=join_code)
    current_question = session.current_question

    if current_question:
        data = {
            "id": str(current_question.id),
            "text": current_question.text,
            "category": current_question.category.name,
            "answers": current_question.get_answers_list(),
        }
    else:
        data = {}

    return JsonResponse(data)


'''

deprecated/not functional: the following functions were my first attempts to trigger communication between admin and participants

'''
@csrf_exempt
@require_POST
def send_question(request):

	data = json.loads(request.body)
	session_code = data.get("session_code")
	question_id = data.get("question_id")

	session = get_object_or_404(Session, join_code=session_code)
	question = get_object_or_404(Question, id=question_id)

	session.current_question = question
	session.save(update_fields=["current_question"])

	# Remove old answers of that question (if any) to start fresh
	ParticipantAnswer.objects.filter(question=question, participant__session=session).delete()

	return JsonResponse({"status": "success"})


@csrf_exempt
@require_POST
def api_submit_answer(request):
	data = json.loads(request.body)
	question_id = data.get("question_id")
	chosen_answer_text = data.get("chosen_answer_text")
	participant_id = data.get("participant_id")

	participant = get_object_or_404(Participant, id=participant_id)
	question = get_object_or_404(Question, id=question_id)

	answer, created = ParticipantAnswer.objects.get_or_create(
		participant=participant,
		question=question,
		defaults={"chosen_answer": chosen_answer_text},
	)
	if not created:
		return JsonResponse({"status": "error", "message": "Antwort bereits abgegeben."})

	# Admin bewertet später → 0 Punkte erst einmal
	return JsonResponse({"status": "success", "message": "Antwort gespeichert!"})


@csrf_exempt
@require_POST
def api_update_answer_points(request):
	data = json.loads(request.body)
	answer_id = data.get("answer_id")
	delta = int(data.get("delta", 0))

	answer = get_object_or_404(ParticipantAnswer, id=answer_id)
	answer.points = (answer.points or 0) + delta
	answer.save(update_fields=["points"])

	# sync to participant.score
	total_score = (
		ParticipantAnswer.objects.filter(participant=answer.participant).aggregate(models.Sum("points"))[
			"points__sum"
		]
		or 0
	)
	answer.participant.score = total_score
	answer.participant.save(update_fields=["score"])

	return JsonResponse({"status": "success", "new_points": answer.points})


def api_get_questions_for_category(request, category_id):
	qs = Question.objects.filter(category_id=category_id).values("id", "text")
	return JsonResponse({"questions": list(qs)})


def api_live_answers(request, session_code):
	session = get_object_or_404(Session, join_code=session_code)
	q = session.current_question
	if not q:
		return JsonResponse({"answers": []})

	answers = ParticipantAnswer.objects.filter(question=q).select_related("participant")
	return JsonResponse(
		{
			"answers": [
				{
					"id": a.id,
					"name": a.participant.name,
					"answer": a.chosen_answer,
					"points": a.points,
				}
				for a in answers
			]
		}
	)


def api_scores(request, session_id):
	participants = Participant.objects.filter(session_id=session_id).values("name", "points")
	return JsonResponse({"scores": list(participants)})
