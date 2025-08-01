from django.db import models
from django.utils import timezone
import uuid


class Category(models.Model):
	id = models.AutoField(primary_key=True)
	name = models.CharField(max_length=120, unique=True)

	def __str__(self):
		return self.name


class Question(models.Model):
	id = models.AutoField(primary_key=True)
	category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="questions")
	question_text = models.TextField()
	correct_answer = models.CharField(max_length=255)
	wrong_answers = models.JSONField(default=list, blank=True)

	def __str__(self):
		return self.question_text[:80]


class Session(models.Model):
	id = models.AutoField(primary_key=True)
	session_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	join_code = models.CharField(max_length=4, unique=True)
	current_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name="current_for_sessions",)

	def __str__(self):
		return f"Session {self.join_code}"


class Participant(models.Model):
	id = models.AutoField(primary_key=True)
	session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="participants")
	name = models.CharField(max_length=80)
	points = models.IntegerField(default=0)

	def __str__(self):
		return f"{self.name} ({self.session.join_code})"


class ParticipantAnswer(models.Model):
	id = models.AutoField(primary_key=True)
	#session_id = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="session")
	participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="answers")
	question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="questions")
	chosen_answer = models.CharField(max_length=255)
	points = models.IntegerField(default=0)
	submitted_at = models.DateTimeField(default=timezone.now)

	def __str__(self):
		return f"{self.participant} → {self.chosen_answer} ({self.points})"
