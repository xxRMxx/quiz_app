import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Session, Participant, Question, ParticipantAnswer


class QuizConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_code = self.scope['url_route']['kwargs']['session_code']
        self.room_group_name = f'quiz_{self.session_code}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to quiz session'
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'admin_send_question':
                await self.handle_admin_send_question(text_data_json)
            elif message_type == 'participant_submit_answer':
                await self.handle_participant_submit_answer(text_data_json)
            elif message_type == 'admin_update_points':
                await self.handle_admin_update_points(text_data_json)
            elif message_type == 'admin_show_answers':
                await self.handle_admin_show_answers(text_data_json)
            elif message_type == 'admin_show_leaderboard':
                await self.handle_admin_show_leaderboard(text_data_json)
            elif message_type == 'participant_join':
                await self.handle_participant_join(text_data_json)
            elif message_type == 'ping':
                await self.handle_ping()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def handle_admin_send_question(self, data):
        """Handle admin sending a new question"""
        question_id = data.get('question_id')
        session = await self.get_session()
        
        if not session:
            return
            
        question = await self.get_question(question_id)
        if not question:
            return

        # Update session with new question
        await self.update_session_question(session, question)
        
        # Get shuffled answers for participants
        answers = await self.get_question_answers(question)
        
        # Broadcast new question to all participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'new_question',
                'question': {
                    'id': question.id,
                    'text': question.question_text,
                    'category': question.category.name,
                    'answers': answers,
                    'time_limit': question.time_limit,
                    'points': question.points,
                    'number': session.current_question_number
                }
            }
        )

        # Send admin confirmation
        await self.send(text_data=json.dumps({
            'type': 'question_sent',
            'message': 'Question sent successfully'
        }))

    async def handle_participant_submit_answer(self, data):
        """Handle participant submitting an answer"""
        participant_id = data.get('participant_id')
        question_id = data.get('question_id')
        chosen_answer = data.get('chosen_answer')
        time_taken = data.get('time_taken', None)

        # Save the answer
        answer = await self.save_participant_answer(
            participant_id, question_id, chosen_answer, time_taken
        )
        
        if answer:
            # Get updated participant info
            participant = await self.get_participant(participant_id)
            
            # Broadcast to admin dashboard (live answers)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_answered',
                    'answer': {
                        'id': answer.id,
                        'participant_id': participant.id,
                        'participant_name': participant.name,
                        'chosen_answer': chosen_answer,
                        'is_correct': answer.is_correct,
                        'points_awarded': answer.points_awarded,
                        'time_taken': time_taken
                    }
                }
            )

            # Send confirmation to participant
            await self.send(text_data=json.dumps({
                'type': 'answer_submitted',
                'message': 'Answer submitted successfully',
                'is_correct': answer.is_correct,
                'points_awarded': answer.points_awarded
            }))

    async def handle_admin_update_points(self, data):
        """Handle admin manually updating points"""
        answer_id = data.get('answer_id')
        new_points = data.get('new_points')
        
        success = await self.update_answer_points(answer_id, new_points)
        
        if success:
            # Get updated leaderboard
            leaderboard = await self.get_leaderboard()
            
            # Broadcast updated leaderboard
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'leaderboard_updated',
                    'leaderboard': leaderboard
                }
            )

    async def handle_admin_show_answers(self, data):
        """Handle admin revealing correct answers"""
        session = await self.get_session()
        if session and session.current_question:
            await self.update_session_show_answers(session, True)
            
            question = session.current_question
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'show_correct_answer',
                    'correct_answer': question.correct_answer,
                    'explanation': question.explanation
                }
            )

    async def handle_admin_show_leaderboard(self, data):
        """Handle admin showing leaderboard"""
        leaderboard = await self.get_leaderboard()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'show_leaderboard',
                'leaderboard': leaderboard
            }
        )

    async def handle_participant_join(self, data):
        """Handle new participant joining"""
        participant_id = data.get('participant_id')
        participant = await self.get_participant(participant_id)
        
        if participant:
            # Broadcast to admin
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_joined',
                    'participant': {
                        'id': participant.id,
                        'name': participant.name,
                        'points': participant.points
                    }
                }
            )

    async def handle_ping(self):
        """Handle ping for keeping connection alive"""
        await self.send(text_data=json.dumps({
            'type': 'pong'
        }))

    # Event handlers for group messages
    async def new_question(self, event):
        """Send new question to client"""
        await self.send(text_data=json.dumps({
            'type': 'new_question',
            'question': event['question']
        }))

    async def participant_answered(self, event):
        """Send participant answer to admin"""
        await self.send(text_data=json.dumps({
            'type': 'participant_answered',
            'answer': event['answer']
        }))

    async def leaderboard_updated(self, event):
        """Send updated leaderboard"""
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_updated',
            'leaderboard': event['leaderboard']
        }))

    async def show_correct_answer(self, event):
        """Send correct answer reveal"""
        await self.send(text_data=json.dumps({
            'type': 'show_correct_answer',
            'correct_answer': event['correct_answer'],
            'explanation': event.get('explanation')
        }))

    async def show_leaderboard(self, event):
        """Send leaderboard display"""
        await self.send(text_data=json.dumps({
            'type': 'show_leaderboard',
            'leaderboard': event['leaderboard']
        }))

    async def participant_joined(self, event):
        """Send new participant info to admin"""
        await self.send(text_data=json.dumps({
            'type': 'participant_joined',
            'participant': event['participant']
        }))

    # Database operations
    @database_sync_to_async
    def get_session(self):
        try:
            return Session.objects.get(session_code=self.session_code)
        except Session.DoesNotExist:
            return None

    @database_sync_to_async
    def get_question(self, question_id):
        try:
            return Question.objects.select_related('category').get(id=question_id)
        except Question.DoesNotExist:
            return None

    @database_sync_to_async
    def get_participant(self, participant_id):
        try:
            return Participant.objects.get(id=participant_id)
        except Participant.DoesNotExist:
            return None

    @database_sync_to_async
    def update_session_question(self, session, question):
        session.current_question = question
        session.current_question_number += 1
        session.question_start_time = timezone.now()
        session.show_answers = False
        session.save()

    @database_sync_to_async
    def update_session_show_answers(self, session, show_answers):
        session.show_answers = show_answers
        session.save()

    @database_sync_to_async
    def get_question_answers(self, question):
        return question.get_all_answers()

    @database_sync_to_async
    def save_participant_answer(self, participant_id, question_id, chosen_answer, time_taken):
        try:
            participant = Participant.objects.get(id=participant_id)
            question = Question.objects.get(id=question_id)
            
            # Check if answer already exists
            existing_answer = ParticipantAnswer.objects.filter(
                participant=participant,
                question=question
            ).first()
            
            if existing_answer:
                return None  # Already answered
            
            # Create new answer
            answer = ParticipantAnswer.objects.create(
                participant=participant,
                question=question,
                chosen_answer=chosen_answer,
                time_taken=time_taken
            )
            
            return answer
            
        except (Participant.DoesNotExist, Question.DoesNotExist):
            return None

    @database_sync_to_async
    def update_answer_points(self, answer_id, new_points):
        try:
            answer = ParticipantAnswer.objects.get(id=answer_id)
            answer.points_awarded = new_points
            answer.save()
            return True
        except ParticipantAnswer.DoesNotExist:
            return False

    @database_sync_to_async
    def get_leaderboard(self):
        try:
            session = Session.objects.get(session_code=self.session_code)
            participants = session.get_leaderboard()
            
            return [
                {
                    'id': p.id,
                    'name': p.name,
                    'points': p.points,
                    'is_connected': p.is_connected
                }
                for p in participants
            ]
        except Session.DoesNotExist:
            return []