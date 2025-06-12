# quiz_app/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async # get_channel_layer wird hier nicht mehr importiert, es sei denn es wird anderswo benötigt
from .models import QuizSession, Question, Participant, ParticipantAnswer

class QuizConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_code = self.scope['url_route']['kwargs']['session_code']
        self.session_group_name = f'quiz_{self.session_code}'

        await self.channel_layer.group_add(
            self.session_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.session_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'answer_submitted':
            participant_id = text_data_json['participant_id']
            question_id = text_data_json['question_id']
            chosen_answer = text_data_json['answer']

            await self.save_participant_answer(participant_id, question_id, chosen_answer)

            print(f"Antwort empfangen: Teilnehmer {participant_id}, Frage {question_id}, Antwort {chosen_answer}")

        elif message_type == 'register_participant':
            participant_name = text_data_json['name']
            participant = await self.create_participant(participant_name, self.session_code)
            await self.send(text_data=json.dumps({
                'type': 'participant_registered',
                'participant_id': str(participant.participant_id),
                'participant_name': participant.name
            }))
            print(f"Teilnehmer {participant_name} registriert in Session {self.session_code}")

    # Receive message from room group (when Admin sends a question)
    async def quiz_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))

    @sync_to_async
    def create_participant(self, name, session_code):
        session = QuizSession.objects.get(session_code=session_code)
        participant = Participant.objects.create(session=session, name=name)
        return participant

    @sync_to_async
    def save_participant_answer(self, participant_id, question_id, chosen_answer):
        try:
            participant = Participant.objects.get(participant_id=participant_id)
            question = Question.objects.get(id=question_id)
            is_correct = (chosen_answer == question.correct_answer)

            ParticipantAnswer.objects.update_or_create(
                participant=participant,
                question=question,
                defaults={
                    'chosen_answer': chosen_answer,
                    'is_correct': is_correct
                }
            )
            print(f"Antwort von {participant.name} gespeichert. Korrekt: {is_correct}")

        except (Participant.DoesNotExist, Question.DoesNotExist) as e:
            print(f"Fehler beim Speichern der Antwort: {e}")
        except Exception as e:
            print(f"Ein unerwarteter Fehler beim Speichern der Antwort: {e}")

    # Diese Methode wird nicht mehr von views.py aufgerufen, kann entfernt oder angepasst werden
    # Wenn du diese Methode NUR für das Admin-Panel im Backend nutzt, siehe unten
    # @classmethod
    # def send_question_to_session(cls, session_code, question_id):
    #    # ... (Diese Logik wurde in views.py verschoben) ...
    #    pass