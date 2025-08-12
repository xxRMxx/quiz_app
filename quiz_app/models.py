from django.db import models
from django.utils import timezone
from django.db.models import Sum
import uuid
import random
import string


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)


    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()
    correct_answer = models.CharField(max_length=255)
    wrong_answers = models.JSONField(default=list, blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    points = models.IntegerField(default=100, help_text="Points awarded for correct answer")
    time_limit = models.IntegerField(default=30, help_text="Time limit in seconds")
    explanation = models.TextField(blank=True, null=True, help_text="Explanation for the correct answer")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['category', 'question_text']

    def __str__(self):
        return f"{self.category.name}: {self.question_text[:80]}"

    def get_all_answers(self):
        """Returns all answers (correct + wrong) in shuffled order"""
        answers = [self.correct_answer] + self.wrong_answers
        random.shuffle(answers)
        return answers

    def get_answers_with_labels(self):
        """Returns answers with A, B, C, D labels"""
        answers = self.get_all_answers()
        return [(chr(65 + i), answer) for i, answer in enumerate(answers)]


class Session(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting to Start'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('finished', 'Finished'),
    ]
    
    id = models.AutoField(primary_key=True)
    session_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    join_code = models.CharField(max_length=4, unique=True)
    name = models.CharField(max_length=200, default="Quiz Session")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_question = models.ForeignKey(
        Question, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="current_for_sessions"
    )
    current_question_number = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    question_start_time = models.DateTimeField(null=True, blank=True)
    show_answers = models.BooleanField(default=False)
    show_leaderboard = models.BooleanField(default=False)
    
    # Session settings
    auto_advance = models.BooleanField(default=False, help_text="Auto advance to next question")
    show_correct_answer = models.BooleanField(default=True)
    allow_late_joins = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.join_code})"

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = self.generate_join_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_join_code():
        """Generate a unique 4-digit join code"""
        while True:
            code = ''.join(random.choices(string.digits, k=4))
            if not Session.objects.filter(join_code=code).exists():
                return code

    def start_session(self):
        """Start the session"""
        self.status = 'active'
        self.started_at = timezone.now()
        self.save()

    def finish_session(self):
        """Finish the session"""
        self.status = 'finished'
        self.finished_at = timezone.now()
        self.save()

    def get_leaderboard(self):
        """Get participants ordered by points"""
        return self.participants.all().order_by('-points', 'name')


class Participant(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="participants")
    name = models.CharField(max_length=80)
    points = models.IntegerField(default=0)
    is_connected = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['session', 'name']
        ordering = ['-points', 'name']

    def __str__(self):
        return f"{self.name} ({self.session.join_code}) - {self.points} pts"

    def get_current_answer(self, question):
        """Get participant's answer for a specific question"""
        try:
            return self.answers.get(question=question)
        except ParticipantAnswer.DoesNotExist:
            return None

    def get_correct_answers_count(self):
        """Get count of correct answers"""
        return self.answers.filter(is_correct=True).count()

    def get_total_answers_count(self):
        """Get total count of answers"""
        return self.answers.count()

    def get_accuracy_percentage(self):
        """Get accuracy as percentage"""
        total = self.get_total_answers_count()
        if total == 0:
            return 0
        correct = self.get_correct_answers_count()
        return round((correct / total) * 100, 1)


class ParticipantAnswer(models.Model):
    id = models.AutoField(primary_key=True)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="participant_answers")
    chosen_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    points_awarded = models.IntegerField(default=0)
    time_taken = models.FloatField(null=True, blank=True, help_text="Time in seconds to answer")
    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['participant', 'question']
        ordering = ['submitted_at']

    def __str__(self):
        return f"{self.participant.name} → {self.chosen_answer} ({self.points_awarded} pts)"

    def save(self, *args, **kwargs):
        # Check if answer is correct
        self.is_correct = self.chosen_answer == self.question.correct_answer
        
        # Calculate points if not manually set
        if self.is_correct and self.points_awarded == 0:
            self.points_awarded = self.question.points
            
            # Bonus points for speed (if time_taken is available)
            if self.time_taken and self.time_taken < 5:
                self.points_awarded += 50  # Speed bonus
        
        super().save(*args, **kwargs)
        
        # Update participant's total points
        self.update_participant_points()

    def update_participant_points(self):
        """Update participant's total points"""
        total_points = ParticipantAnswer.objects.filter(
            participant=self.participant
        ).aggregate(
            total=Sum('points_awarded')
        )['total'] or 0
        
        self.participant.points = total_points
        self.participant.save(update_fields=['points'])


class SessionQuestion(models.Model):
    """Many-to-many through model for session questions with order"""
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['session', 'question']
        ordering = ['order']

    def __str__(self):
        return f"{self.session.name} - Q{self.order}: {self.question.question_text[:50]}"