# quiz_app/admin.py
from django.contrib import admin
from .models import Question, QuizSession, Participant, ParticipantAnswer
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'correct_answer')
    search_fields = ('text',)

@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    # 'name' ist das erste Feld in list_display
    list_display = ('name', 'join_code', 'session_code', 'is_active', 'current_question')
    # 'name' und 'join_code' sind in list_editable
    list_editable = ('is_active', 'current_question', 'name', 'join_code')
    
    # FIX: Explicitly set list_display_links.
    # Da 'name' (das erste Feld in list_display) auch in list_editable ist,
    # MÜSSEN wir ein anderes Feld als Link definieren. 'session_code' ist hier ideal.
    list_display_links = ('session_code',) 

    readonly_fields = ('session_code',) 

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if 'current_question' in form.changed_data and obj.current_question:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                messages.error(request, "Channels Layer nicht verfügbar. Frage konnte nicht via WebSocket gesendet werden.")
                print("Fehler: Channels Layer ist nicht verfügbar im Admin-Kontext.")
                return

            question = obj.current_question
            message_data = {
                'type': 'new_question',
                'question_id': question.id,
                'question_text': question.text,
                'answers': question.get_all_answers(),
            }

            try:
                async_to_sync(channel_layer.group_send)(
                    f'quiz_{obj.session_code}',
                    {
                        'type': 'quiz_message',
                        'message': message_data
                    }
                )
                print(f"Frage {question.id} von Admin-Panel an Session {obj.session_code} via WebSocket gesendet.")
                messages.success(request, "Frage erfolgreich via WebSocket gesendet.")
            except Exception as e:
                print(f"Fehler beim Senden der Frage vom Admin-Panel via WebSocket: {str(e)}")
                messages.error(request, f"Fehler beim Senden der Frage via WebSocket: {str(e)}")


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'participant_id')
    list_filter = ('session',)

@admin.register(ParticipantAnswer)
class ParticipantAnswerAdmin(admin.ModelAdmin):
    list_display = ('participant', 'question', 'chosen_answer', 'is_correct', 'timestamp')
    list_filter = ('participant__session', 'question', 'is_correct')
    readonly_fields = ('participant', 'question', 'chosen_answer', 'is_correct', 'timestamp')