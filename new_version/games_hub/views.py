import random
import string
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Max
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.db.models import Sum, F, Case, When, Value, IntegerField, Q
from django.db import connection
from .models import HubSession, HubParticipant, HubGameStep, GameVote
from QuizGame.models import Quiz as QuizGameModel, QuizParticipant, QuizQuestion
from sorting_ladder.models import SortingLadderGame, SortingLadderParticipant, SortingQuestion
from clue_rush.models import ClueRushGame, ClueRushParticipant
from Assign.models import AssignQuiz, AssignParticipant
from Estimation.models import EstimationQuiz, EstimationParticipant
from where_is_this.models import WhereQuiz, WhereParticipant
from who_is_lying.models import WhoQuiz, WhoParticipant
from who_is_that.models import WhoThatQuiz, WhoThatParticipant
from black_jack_quiz.models import BlackJackQuiz, BlackJackParticipant


def gen_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@login_required
@require_http_methods(["GET", "POST"])
def create_session(request):
    if request.method == 'POST':
        name = request.POST.get('name') or ''
        games_weight = request.POST.get('games_weight') or 2.0
        # Get the ordered list of games from the hidden input
        games_order_json = request.POST.get('games_order', '[]')
        
        try:
            # Parse the JSON array of game keys in the order they were selected
            games_ordered = json.loads(games_order_json)
            if not isinstance(games_ordered, list):
                games_ordered = []
        except json.JSONDecodeError:
            games_ordered = []
            
        # Fallback to the original games list if no order is provided
        if not games_ordered:
            games_ordered = request.POST.getlist('games')

        code = request.POST.get('code') or gen_code()
        
        if HubSession.objects.filter(code=code).exists():
            return render(request, 'hub/create_session.html', {
                'error': 'A session with this code already exists. Please choose a different code.',
                'quiz_questions': QuizQuestion.objects.filter(is_active=True).order_by('-created_at'),
                'sorting_questions': SortingQuestion.objects.filter(is_active=True).order_by('question_text'),
            })
            
        # Reset all existing quizzes to 'waiting' so they can be reused for this new session
        try:
            QuizGameModel.objects.update(status='waiting')
            AssignQuiz.objects.update(status='waiting')
            ClueRushGame.objects.update(status='waiting')
            EstimationQuiz.objects.update(status='waiting')
            WhereQuiz.objects.update(status='waiting')
            WhoQuiz.objects.update(status='waiting')
            WhoThatQuiz.objects.update(status='waiting')
            BlackJackQuiz.objects.update(status='waiting')
            SortingLadderGame.objects.update(status='waiting')
        except Exception:
            pass

        # Create the session
        session = HubSession.objects.create(code=code, name=name, games_weight=games_weight)
        
        # Create game steps in the selected order
        for order, game_key in enumerate(games_ordered):
            if not game_key:
                continue
                
            # Create the game step
            step = HubGameStep.objects.create(
                session=session,
                order=order,
                game_key=game_key
            )
            
            # Auto-create the per-game quiz and attach room_code
            quiz_title = f"{name} - {game_key.replace('_', ' ').title()}"
            room_code = auto_create_game_quiz(game_key, request.user, quiz_title)
            
            if room_code:
                step.room_code = room_code
                step.title = quiz_title
                step.save()
                
        # Associate selected questions with each quiz instance
        for order, game_key in enumerate(games_ordered):
            if not game_key:
                continue
            try:
                step = HubGameStep.objects.get(session=session, order=order)
                if game_key == 'quiz' and step.room_code:
                    question_ids = request.POST.getlist('quiz_question_ids')
                    if question_ids:
                        quiz_obj = QuizGameModel.objects.get(room_code=step.room_code)
                        quiz_obj.selected_questions.set(
                            QuizQuestion.objects.filter(id__in=question_ids)
                        )
                elif game_key == 'sorting_ladder' and step.room_code:
                    question_ids = request.POST.getlist('sorting_question_ids')
                    if question_ids:
                        sl_obj = SortingLadderGame.objects.get(room_code=step.room_code)
                        sl_obj.selected_questions.set(
                            SortingQuestion.objects.filter(id__in=question_ids)
                        )
            except Exception:
                pass

        return redirect('games_hub:monitor', session_code=code)

    # GET request - show the form with available questions
    quiz_questions = QuizQuestion.objects.filter(is_active=True).order_by('-created_at')
    sorting_questions = SortingQuestion.objects.filter(is_active=True).order_by('question_text')
    return render(request, 'hub/create_session.html', {
        'quiz_questions': quiz_questions,
        'sorting_questions': sorting_questions,
    })


def get_game_participant_data(session, game_model, participant_model, room_code, game_key):
    """Helper function to get participant data for a specific game"""
    try:
        game = game_model.objects.get(room_code=room_code)
        # Only include participants who joined during this session's window
        participants_qs = participant_model.objects.filter(quiz=game, hub_session_code=session.code).select_related('quiz')
        if session.started_at:
            participants_qs = participants_qs.filter(joined_at__gte=session.started_at)
        if session.ended_at:
            participants_qs = participants_qs.filter(joined_at__lte=session.ended_at)
        participants = participants_qs
        
        data = {}
        for p in participants:
            # Some games (e.g., BlackJack) track total_points instead of total_score
            score_value = getattr(p, 'total_score', None)
            if score_value is None:
                score_value = getattr(p, 'total_points', 0)
            accuracy_fn = getattr(p, 'get_average_accuracy', None)
            accuracy_value = accuracy_fn() if callable(accuracy_fn) else 0
            data[p.name] = {
                'score': score_value,
                'accuracy': accuracy_value
            }
        return data
    except game_model.DoesNotExist:
        return {}

def get_leaderboard_data(session):
    """Generate leaderboard data for a session"""

    try:
        # Get all game steps for the session
        steps = session.steps.all().order_by('order')
        
        # Initialize response data
        games = []
        participants_data = {}
        instance_meta = {}
        
        # Map of game keys to their models and participant models
        # Keys must match HubGameStep.game_key values used throughout the app
        GAME_MODELS = {
            'quiz': (QuizGameModel, QuizParticipant, 'Quiz Game'),
            'clue_rush': (ClueRushGame, ClueRushParticipant, 'Clue Rush Game'),
            'estimation': (EstimationQuiz, EstimationParticipant, 'Estimation'),
            'assign': (AssignQuiz, AssignParticipant, 'Assign'),
            'who': (WhoQuiz, WhoParticipant, 'Who is Lying?'),
            'who_that': (WhoThatQuiz, WhoThatParticipant, 'Who is That?'),
            'where': (WhereQuiz, WhereParticipant, 'Where is This?'),
            'blackjack': (BlackJackQuiz, BlackJackParticipant, 'Black Jack'),
            'sorting_ladder': (SortingLadderGame, SortingLadderParticipant, 'Sorting Ladder')
        }
        
        # Process each game step
        for step in steps:
            game_key = step.game_key
            if game_key not in [g['key'] for g in games]:
                games.append({
                    'key': game_key,
                    'name': next((g[2] for k, g in GAME_MODELS.items() if k == game_key), game_key.title())
                })

            # Get participant data for this specific game instance (room)
            if game_key in GAME_MODELS and GAME_MODELS[game_key][1] is not None:
                game_model, participant_model, _ = GAME_MODELS[game_key]
                game_data = get_game_participant_data(session, game_model, participant_model, step.room_code, game_key)

                # Use a per-instance key so multiple steps of same type don't overwrite
                instance_key = f"{game_key}:{step.room_code}"

                # Record instance display metadata (title and type)
                type_name = next((g[2] for k, g in GAME_MODELS.items() if k == game_key), game_key.title())
                # Prefer the actual quiz object's title; fallback to step.title if present
                game_obj = None
                try:
                    game_obj = game_model.objects.only('title').get(room_code=step.room_code)
                except Exception:
                    game_obj = None
                game_title = (getattr(game_obj, 'title', None) or getattr(step, 'title', '') or '')
                instance_meta[instance_key] = {
                    'title': game_title,
                    'type': type_name,
                }

                # Determine winner score for this game (1 hub point per game win)
                max_score = max((d['score'] for d in game_data.values()), default=0)

                # Update participants data
                for name, data in game_data.items():
                    if name not in participants_data:
                        participants_data[name] = {
                            'name': name,
                            'total_score': 0,
                            'weighted_score': 0,
                            'games_played': 0,
                            'game_scores': {},
                            'game_accuracies': {}
                        }

                    # Count every game instance played
                    participants_data[name]['games_played'] += 1

                    # Store scores per instance to avoid overwriting when multiple steps exist
                    participants_data[name]['game_scores'][instance_key] = data['score']
                    participants_data[name]['game_accuracies'][instance_key] = data['accuracy']
                    participants_data[name]['total_score'] += data['score']

                    # Winner gets 1 hub point; ties share the point; 0 if no one scored
                    if max_score > 0 and data['score'] == max_score:
                        participants_data[name]['weighted_score'] += 1
        
        # Apply score adjustments from HubParticipant
        hub_participants = {
            hp.nickname: hp
            for hp in HubParticipant.objects.filter(session=session)
        }
        for name, pdata in participants_data.items():
            hp = hub_participants.get(name)
            pdata['hub_participant_id'] = hp.id if hp else None
            pdata['score_adjustment'] = hp.score_adjustment if hp else 0
            pdata['total_score'] += hp.score_adjustment if hp else 0

        # Convert to list and sort by weighted score
        participants = sorted(participants_data.values(), key=lambda x: x['weighted_score'], reverse=True)
    except Exception as e:
        print("Error getting leaderboard data:", e)
    return {
        'games': games,
        'participants': participants,
        'instances': instance_meta,
    }

@login_required
@require_POST
def set_hub_participant_score(request):
    """Manually set the score adjustment for a HubParticipant."""
    try:
        data = json.loads(request.body)
        participant = get_object_or_404(HubParticipant, id=data['participant_id'])
        participant.score_adjustment = int(data['score'])
        participant.save(update_fields=['score_adjustment'])
        return JsonResponse({'success': True, 'new_score': participant.score_adjustment})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def session_leaderboard_api(request, session_code):
    """API endpoint to get leaderboard data for a session"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        session = HubSession.objects.get(code=session_code)
        data = get_leaderboard_data(session)
        return JsonResponse(data)
    except HubSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def lobby(request, session_code: str):
    session = get_object_or_404(HubSession, code=session_code)
    participants = HubParticipant.objects.filter(session=session)
    
    return render(request, 'hub/lobby.html', {
        'session_code': session_code,
        'participants': list(participants.values('id', 'nickname'))
    })

def session_leaderboard(request, session_code: str):
    """Display the final leaderboard for a session."""
    session = get_object_or_404(HubSession, code=session_code)
    leaderboard_data = get_leaderboard_data(session)
    
    # Convert the data to a JSON string for the template
    leaderboard_json = json.dumps(leaderboard_data['participants'], default=str)
    instance_meta_json = json.dumps(leaderboard_data.get('instances', {}), default=str)
    
    #Check if user is admin
    is_admin = False
    if request.user.is_superuser or request.user.is_staff:
        is_admin = True
    
    return render(request, 'hub/leaderboard.html', {
        'session': session,
        'leaderboard_data': leaderboard_json,  # Pass as JSON string
        'participants': leaderboard_data['participants'],    # Also pass as Python object for template loops
        'instance_meta_json': instance_meta_json,
        'is_admin': is_admin
    })

def monitor(request, session_code: str):
    session = get_object_or_404(HubSession, code=session_code)
    steps = session.steps.all()

    # Gather waiting games grouped by type for the current user
    user = request.user
    waiting_games = {
        'quiz': QuizGameModel.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'clue_rush': ClueRushGame.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'assign': AssignQuiz.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'estimation': EstimationQuiz.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'where': WhereQuiz.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'who': WhoQuiz.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'who_that': WhoThatQuiz.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'blackjack': BlackJackQuiz.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
        'sorting_ladder': SortingLadderGame.objects.filter(status='waiting', creator=user).values('title', 'room_code'),
    }

    # All lobby participants for the right column
    session_players = list(
        session.participants.order_by('joined_at').values('id', 'nickname', 'score_adjustment')
    )
    from .utils import get_server_ip
    ip = get_server_ip()
    return render(request, 'hub/monitor.html', {
        'session': session,
        'steps': steps,
        'ip': ip,
        'waiting_games': waiting_games,
        'session_players': session_players,
    })


@login_required
@require_POST
def add_step_to_session(request, session_code):
    """Add a new game step to a running session."""
    session = get_object_or_404(HubSession, code=session_code)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    game_key = data.get('game_key', '').strip()
    title = data.get('title', '').strip()
    question_ids = data.get('question_ids', [])

    valid_keys = [choice[0] for choice in HubGameStep.GAME_CHOICES]
    if game_key not in valid_keys:
        return JsonResponse({'error': 'Invalid game type'}, status=400)

    next_order = (session.steps.aggregate(Max('order'))['order__max'] or -1) + 1
    quiz_title = title or f"{session.name or session.code} - {game_key.replace('_', ' ').title()} {next_order + 1}"
    room_code = auto_create_game_quiz(game_key, request.user, quiz_title)
    if not room_code:
        return JsonResponse({'error': 'Game could not be created'}, status=500)

    # Assign selected questions to the newly created quiz
    if question_ids:
        _assign_questions_to_quiz(game_key, room_code, question_ids)

    step = HubGameStep.objects.create(
        session=session,
        order=next_order,
        game_key=game_key,
        room_code=room_code,
        title=quiz_title,
    )
    return JsonResponse({
        'success': True,
        'step': {
            'order': step.order,
            'game_key': step.game_key,
            'game_key_display': step.get_game_key_display(),
            'room_code': step.room_code,
            'title': step.title,
        }
    })


def _assign_questions_to_quiz(game_key: str, room_code: str, question_ids: list):
    """Assign selected question IDs to a newly created quiz via selected_questions."""
    from QuizGame.models import QuizQuestion
    from Assign.models import AssignQuestion
    from Estimation.models import EstimationQuestion
    from where_is_this.models import WhereQuestion
    from who_is_lying.models import WhoQuestion
    from who_is_that.models import WhoThatQuestion
    from black_jack_quiz.models import BlackJackQuestion
    from sorting_ladder.models import SortingQuestion
    from clue_rush.models import ClueQuestion

    quiz_model_map = {
        'quiz':           (QuizGameModel,      QuizQuestion),
        'assign':         (AssignQuiz,         AssignQuestion),
        'estimation':     (EstimationQuiz,     EstimationQuestion),
        'where':          (WhereQuiz,          WhereQuestion),
        'who':            (WhoQuiz,            WhoQuestion),
        'who_that':       (WhoThatQuiz,        WhoThatQuestion),
        'blackjack':      (BlackJackQuiz,      BlackJackQuestion),
        'sorting_ladder': (SortingLadderGame,  SortingQuestion),
        'clue_rush':      (ClueRushGame,       ClueQuestion),
    }
    entry = quiz_model_map.get(game_key)
    if not entry:
        return
    quiz_model, question_model = entry
    try:
        quiz = quiz_model.objects.get(room_code=room_code)
        questions = question_model.objects.filter(id__in=question_ids)
        quiz.selected_questions.set(questions)
    except Exception:
        pass


def auto_create_game_quiz(game_key: str, user, title: str):
    """Create a quiz instance for the given game and return its room_code."""
    try:
        if game_key == 'quiz':
            obj = QuizGameModel.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'clue_rush':
            obj = ClueRushGame.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'assign':
            obj = AssignQuiz.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'estimation':
            obj = EstimationQuiz.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'where':
            obj = WhereQuiz.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'who':
            obj = WhoQuiz.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'who_that':
            obj = WhoThatQuiz.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'blackjack':
            obj = BlackJackQuiz.objects.create(creator=user, title=title)
            return obj.room_code
        if game_key == 'sorting_ladder':
            obj = SortingLadderGame.objects.create(creator=user, title=title)
            return obj.room_code
    except Exception:
        return None
    return None


@login_required
def get_available_questions(request, game_key):
    """Return available questions for a given game type."""
    from QuizGame.models import QuizQuestion
    from Assign.models import AssignQuestion
    from Estimation.models import EstimationQuestion
    from where_is_this.models import WhereQuestion
    from who_is_lying.models import WhoQuestion
    from who_is_that.models import WhoThatQuestion
    from black_jack_quiz.models import BlackJackQuestion
    from sorting_ladder.models import SortingQuestion
    from clue_rush.models import ClueQuestion

    config = {
        'quiz':           (QuizQuestion,       'question_text'),
        'assign':         (AssignQuestion,      'question_text'),
        'estimation':     (EstimationQuestion,  'question_text'),
        'where':          (WhereQuestion,       'question_text'),
        'who':            (WhoQuestion,         'statement'),
        'who_that':       (WhoThatQuestion,     'question_text'),
        'blackjack':      (BlackJackQuestion,   'question_text'),
        'sorting_ladder': (SortingQuestion,     'question_text'),
        'clue_rush':      (ClueQuestion,        'question_text'),
    }
    entry = config.get(game_key)
    if not entry:
        return JsonResponse({'error': 'Unknown game type'}, status=400)

    model, text_field = entry
    questions = [
        {'id': q.id, 'text': getattr(q, text_field, '')}
        for q in model.objects.all().order_by('id')
    ]
    return JsonResponse({'questions': questions})


@login_required
@require_POST
def reorder_steps(request, session_code):
    """Reorder game steps. Body: {order: [step_id, step_id, ...]} (list of step PKs in new order)."""
    try:
        data = json.loads(request.body)
        step_ids = data.get('order', [])
        session = get_object_or_404(HubSession, code=session_code)
        steps = {s.id: s for s in session.steps.all()}
        for new_order, step_id in enumerate(step_ids):
            step = steps.get(int(step_id))
            if step and step.order != new_order:
                step.order = new_order
                step.save(update_fields=['order'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_POST
def submit_vote(request, session_code):
    """Participant submits a vote for the next game."""
    try:
        data = json.loads(request.body)
        nickname = data.get('nickname', '').strip()
        step_order = data.get('step_order')
        if not nickname or step_order is None:
            return JsonResponse({'success': False, 'error': 'Missing nickname or step_order'}, status=400)

        session = get_object_or_404(HubSession, code=session_code)
        step = get_object_or_404(HubGameStep, session=session, order=step_order)

        vote, created = GameVote.objects.update_or_create(
            session=session,
            participant_nickname=nickname,
            defaults={'step': step},
        )

        votes = _get_vote_counts(session)
        return JsonResponse({'success': True, 'created': created, 'votes': votes})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def get_votes(request, session_code):
    """Return current vote counts for a session."""
    session = get_object_or_404(HubSession, code=session_code)
    votes = _get_vote_counts(session)
    return JsonResponse({'votes': votes})


def _get_vote_counts(session):
    """Helper: return list of {step_order, game_key, title, count} sorted by count desc."""
    from django.db.models import Count
    steps = session.steps.all()
    vote_qs = GameVote.objects.filter(session=session).values('step_id').annotate(count=Count('id'))
    vote_map = {v['step_id']: v['count'] for v in vote_qs}
    result = []
    for step in steps:
        result.append({
            'step_order': step.order,
            'game_key': step.game_key,
            'title': step.title or step.get_game_key_display(),
            'count': vote_map.get(step.id, 0),
        })
    result.sort(key=lambda x: x['count'], reverse=True)
    return result
