from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
import json

from .models import (
    Category, 
    Question, 
    Session, 
    Participant, 
    ParticipantAnswer, 
    SessionQuestion
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'question_count', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['created_at']
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ['question_text', 'difficulty', 'points', 'time_limit']
    readonly_fields = []


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        'question_text_short', 'category', 'difficulty', 
        'points', 'time_limit', 'created_at'
    ]
    list_filter = ['category', 'difficulty', 'created_at']
    search_fields = ['question_text', 'correct_answer']
    
    fieldsets = (
        ('Question Details', {
            'fields': ('category', 'question_text', 'difficulty')
        }),
        ('Answers', {
            'fields': ('correct_answer', 'wrong_answers_display', 'explanation')
        }),
        ('Settings', {
            'fields': ('points', 'time_limit')
        }),
    )
    
    readonly_fields = ['wrong_answers_display']
    
    def question_text_short(self, obj):
        return obj.question_text[:80] + "..." if len(obj.question_text) > 80 else obj.question_text
    question_text_short.short_description = 'Question'
    
    def wrong_answers_display(self, obj):
        if obj.wrong_answers:
            return format_html(
                '<ul>{}</ul>',
                ''.join([f'<li>{answer}</li>' for answer in obj.wrong_answers])
            )
        return "No wrong answers"
    wrong_answers_display.short_description = 'Wrong Answers'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text for wrong_answers field
        if 'wrong_answers' in form.base_fields:
            form.base_fields['wrong_answers'].help_text = 'Enter wrong answers as JSON array, e.g., ["Wrong 1", "Wrong 2", "Wrong 3"]'
        return form


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    readonly_fields = ['joined_at', 'last_seen', 'points']
    fields = ['name', 'points', 'is_connected', 'joined_at']


class SessionQuestionInline(admin.TabularInline):
    model = SessionQuestion
    extra = 0
    readonly_fields = ['started_at', 'completed_at']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'join_code', 'status', 'participant_count', 
        'current_question_number', 'created_at', 'session_actions'
    ]
    list_filter = ['status', 'created_at', 'allow_late_joins']
    search_fields = ['name', 'join_code']
    readonly_fields = [
        'session_code', 'join_code', 'created_at', 
        'started_at', 'finished_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'join_code', 'session_code', 'status')
        }),
        ('Current Question', {
            'fields': ('current_question', 'current_question_number', 'question_start_time')
        }),
        ('Settings', {
            'fields': ('auto_advance', 'show_correct_answer', 'allow_late_joins')
        }),
        ('Display Settings', {
            'fields': ('show_answers', 'show_leaderboard')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'finished_at')
        })
    )
    
    inlines = [ParticipantInline, SessionQuestionInline]
    
    actions = ['start_sessions', 'finish_sessions', 'reset_sessions']
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'
    
    def current_question_display(self, obj):
        if obj.current_question:
            return format_html(
                '<strong>Q{}: </strong>{}',
                obj.current_question_number,
                obj.current_question.question_text[:100]
            )
        return "No current question"
    current_question_display.short_description = 'Current Question'
    
    def session_actions(self, obj):
        dashboard_url = f'/admin/{obj.join_code}/'
        
        if obj.status == 'waiting':
            return format_html(
                '<a class="button" href="{}">Dashboard</a>',
                dashboard_url
            )
        elif obj.status == 'active':
            return format_html(
                '<a class="button" href="{}">Dashboard</a>',
                dashboard_url
            )
        elif obj.status == 'finished':
            results_url = f'/session/{obj.join_code}/results/'
            return format_html(
                '<a class="button" href="{}">Dashboard</a> '
                '<a class="button" href="{}">Results</a>',
                dashboard_url, results_url
            )
        return "No actions"
    session_actions.short_description = 'Actions'
    
    def start_sessions(self, request, queryset):
        updated = 0
        for session in queryset.filter(status='waiting'):
            session.start_session()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} session(s) started successfully.',
            messages.SUCCESS
        )
    start_sessions.short_description = "Start selected sessions"
    
    def finish_sessions(self, request, queryset):
        updated = 0
        for session in queryset.filter(status='active'):
            session.finish_session()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} session(s) finished successfully.',
            messages.SUCCESS
        )
    finish_sessions.short_description = "Finish selected sessions"
    
    def reset_sessions(self, request, queryset):
        updated = 0
        for session in queryset:
            session.status = 'waiting'
            session.current_question = None
            session.current_question_number = 0
            session.started_at = None
            session.finished_at = None
            session.save()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} session(s) reset successfully.',
            messages.SUCCESS
        )
    reset_sessions.short_description = "Reset selected sessions"


class ParticipantAnswerInline(admin.TabularInline):
    model = ParticipantAnswer
    extra = 0
    readonly_fields = ['question', 'is_correct', 'submitted_at', 'time_taken']
    fields = ['question', 'chosen_answer', 'is_correct', 'points_awarded', 'time_taken']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'session', 'points', 'answer_count', 
        'correct_answers', 'is_connected', 'joined_at'
    ]
    list_filter = ['session', 'is_connected', 'joined_at']
    search_fields = ['name', 'session__name', 'session__join_code']
    readonly_fields = ['joined_at', 'last_seen', 'points']
    
    inlines = [ParticipantAnswerInline]
    
    def answer_count(self, obj):
        return obj.answers.count()
    answer_count.short_description = 'Answers'
    
    def correct_answers(self, obj):
        correct = obj.answers.filter(is_correct=True).count()
        total = obj.answers.count()
        if total > 0:
            percentage = (correct / total) * 100
            return f"{correct}/{total} ({percentage:.1f}%)"
        return "0/0"
    correct_answers.short_description = 'Correct'


@admin.register(ParticipantAnswer)
class ParticipantAnswerAdmin(admin.ModelAdmin):
    list_display = [
        'participant', 'question_short', 'chosen_answer', 
        'is_correct', 'points_awarded', 'time_taken', 'submitted_at'
    ]
    list_filter = [
        'is_correct', 'submitted_at', 'question__category', 
        'participant__session'
    ]
    search_fields = [
        'participant__name', 'question__question_text', 
        'chosen_answer', 'participant__session__name'
    ]
    readonly_fields = ['is_correct', 'submitted_at']
    
    actions = ['award_bonus_points', 'remove_points', 'mark_correct', 'mark_incorrect']
    
    def question_short(self, obj):
        return obj.question.question_text[:50] + "..."
    question_short.short_description = 'Question'
    
    def award_bonus_points(self, request, queryset):
        for answer in queryset:
            answer.points_awarded += 50
            answer.save()
        
        self.message_user(
            request,
            f'Awarded 50 bonus points to {queryset.count()} answer(s).',
            messages.SUCCESS
        )
    award_bonus_points.short_description = "Award 50 bonus points"
    
    def remove_points(self, request, queryset):
        queryset.update(points_awarded=0)
        self.message_user(
            request,
            f'Removed points from {queryset.count()} answer(s).',
            messages.SUCCESS
        )
    remove_points.short_description = "Remove all points"
    
    def mark_correct(self, request, queryset):
        for answer in queryset:
            answer.is_correct = True
            if answer.points_awarded == 0:
                answer.points_awarded = answer.question.points
            answer.save()
        
        self.message_user(
            request,
            f'Marked {queryset.count()} answer(s) as correct.',
            messages.SUCCESS
        )
    mark_correct.short_description = "Mark as correct"
    
    def mark_incorrect(self, request, queryset):
        queryset.update(is_correct=False, points_awarded=0)
        self.message_user(
            request,
            f'Marked {queryset.count()} answer(s) as incorrect.',
            messages.SUCCESS
        )
    mark_incorrect.short_description = "Mark as incorrect"


@admin.register(SessionQuestion)
class SessionQuestionAdmin(admin.ModelAdmin):
    list_display = [
        'session', 'order', 'question_short', 'is_completed', 
        'started_at', 'completed_at'
    ]
    list_filter = ['is_completed', 'session', 'question__category']
    search_fields = ['session__name', 'question__question_text']
    
    def question_short(self, obj):
        return obj.question.question_text[:50] + "..."
    question_short.short_description = 'Question'


# Custom admin site configuration
admin.site.site_header = "Quiz Management System"
admin.site.site_title = "Quiz Admin"
admin.site.index_title = "Welcome to Quiz Administration"

# Add custom CSS for better styling
class QuizAdminConfig:
    def ready(self):
        pass