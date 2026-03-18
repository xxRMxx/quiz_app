from django.db import models
from games_website.models import SyncBase
from django.utils import timezone


class HubSession(SyncBase):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    current_step_index = models.IntegerField(default=0)
    games_weight = models.FloatField(default=2.0)

    def __str__(self):
        return f"HubSession {self.code}"


class HubParticipant(SyncBase):
    session = models.ForeignKey(HubSession, related_name='participants', on_delete=models.CASCADE)
    nickname = models.CharField(max_length=50)
    joined_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(default=timezone.now)
    score_adjustment = models.IntegerField(default=0)

    class Meta:
        unique_together = ('session', 'nickname')

    def __str__(self):
        return f"{self.nickname} ({self.session.code})"


class HubGameStep(SyncBase):
    GAME_CHOICES = [
        ('quiz', 'QuizGame'),
        ('assign', 'Assign'),
        ('estimation', 'Estimation'),
        ('where', 'Where Is This'),
        ('who', 'Who Is Lying'),
        ('who_that', 'Who Is That'),
        ('blackjack', 'Black Jack Quiz'),
        ('sorting_ladder', 'Sorting Ladder'),
    ]
    session = models.ForeignKey(HubSession, related_name='steps', on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    game_key = models.CharField(max_length=20, choices=GAME_CHOICES)
    room_code = models.CharField(max_length=16, blank=True)
    title = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ('session', 'order')

    def __str__(self):
        return f"{self.order}: {self.get_game_key_display()} ({self.session.code})"


class GameVote(models.Model):
    session = models.ForeignKey(HubSession, related_name='votes', on_delete=models.CASCADE)
    participant_nickname = models.CharField(max_length=50)
    step = models.ForeignKey(HubGameStep, related_name='votes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('session', 'participant_nickname')

    def __str__(self):
        return f"{self.participant_nickname} → {self.step} ({self.session.code})"
