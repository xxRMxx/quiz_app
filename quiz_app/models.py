# quiz_app/models.py
from django.db import models
import uuid # Für eindeutige Session-IDs
import random # Neu importieren für den vierstelligen Code

class Question(models.Model):
    text = models.CharField(max_length=255)
    correct_answer = models.CharField(max_length=255)
    wrong_answer_1 = models.CharField(max_length=255)
    wrong_answer_2 = models.CharField(max_length=255)
    wrong_answer_3 = models.CharField(max_length=255)

    def __str__(self):
        return self.text

    def get_all_answers(self):
        """Gibt alle Antwortmöglichkeiten in zufälliger Reihenfolge zurück."""
        answers = [self.correct_answer, self.wrong_answer_1, self.wrong_answer_2, self.wrong_answer_3]
        import random
        random.shuffle(answers)
        return answers

class QuizSession(models.Model):
    session_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # NEU: Vierstelliger, menschlich lesbarer Code für den Beitritt
    join_code = models.CharField(max_length=4, unique=True, blank=True, null=True) 
    name = models.CharField(max_length=100, default="Mein Quiz") # Optional: Session-Name

    current_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Generiere einen join_code, wenn noch keiner vorhanden ist
        if not self.join_code:
            self.join_code = self._generate_unique_join_code()
        super().save(*args, **kwargs)

    def _generate_unique_join_code(self):
        """Generiert einen eindeutigen 4-stelligen numerischen Code."""
        while True:
            code = str(random.randint(0, 9999)).zfill(4) # 4-stellige Zahl (z.B. "0042")
            if not QuizSession.objects.filter(join_code=code).exists():
                return code

    def __str__(self):
        # Zeigt den join_code an, wenn verfügbar, sonst die UUID
        return f"Session {self.join_code or self.session_code} - {self.name}"

class Participant(models.Model):
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    participant_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.name

class ParticipantAnswer(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    chosen_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {self.question.text[:20]} - {self.chosen_answer}"