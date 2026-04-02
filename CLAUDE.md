# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands require the virtual environment to be active:

```bash
source .venv/bin/activate
```

```bash
# Run dev server (HTTP only)
python manage.py runserver

# Run dev server with WebSocket support
daphne -b 0.0.0.0 -p 8000 games_website.asgi:application

# Migrations
python manage.py migrate
python manage.py makemigrations <app_name>

# Tests
python manage.py test
python manage.py test <app_name>
python manage.py test <app_name>.tests.TestClassName.test_method  # single test

# Seed local DB with test data (18 game instances + 1 hub session)
python seed_test_data.py           # anlegen
python seed_test_data.py --clear   # löschen + neu anlegen

# Code formatting
black .
```

> **Static files with Daphne**: `runserver` serves static files automatically. Daphne does not — wrap the app with `ASGIStaticFilesHandler` in `asgi.py` or serve via nginx/whitenoise in production.

## Architecture

### Project layout

The application lives at the repository root. Django project module: `games_website` (settings, urls, asgi).

### Django apps

| App | URL prefix | Purpose |
|-----|------------|---------|
| `games_hub` | `/hub/` | Central hub: multi-game sessions, lobby, leaderboard, voting |
| `admin_dashboard` | `/admin-dashboard/` | Host-facing UI: game management, session monitoring, question banks |
| `QuizGame` | `/quiz/` | Multiple-choice quiz |
| `Assign` | `/assign/` | Drag-and-drop matching |
| `Estimation` | `/estimation/` | Numerical estimation |
| `where_is_this` | `/where/` | Map-based location game |
| `who_is_lying` | `/who/` | Identify liars from statements |
| `who_is_that` | `/who-is-that/` | Identify person from image |
| `black_jack_quiz` | `/blackjack/` | Numerical trivia in a Blackjack format |
| `sorting_ladder` | `/sorting-ladder/` | Sort items by a given criterion |
| `clue_rush` | `/clue-rush/` | Timed trivia with progressive clues |

### Hub session flow

`games_hub` is the orchestration layer that ties everything together:

1. Host creates a `HubSession` (generates a unique `code`).
2. Host adds `HubGameStep` entries (game type + room code + order) via the Session Monitor.
3. Participants join via `/hub/lobby/<code>/` and can vote on which game to play next (`GameVote`).
4. Host starts a game from the Session Monitor → all lobby participants are redirected automatically via WebSocket.
5. After each game, participants return to the lobby; scores aggregate into a session leaderboard.

### Real-time communication

Django Channels is used throughout. The WebSocket URL pattern is `ws/<game>/` per app, plus `ws/hub/<session_code>/` for the hub.

- **Development**: `InMemoryChannelLayer` (no Redis needed)
- **Production**: `RedisChannelLayer` on `127.0.0.1:6379`

Each game app has a `consumers.py`. Channel layer config is in `games_website/settings.py`.

#### Hub WebSocket message types (`ws/hub/<session_code>/`)

**Client → Server:**
- `join` — `{type, nickname}`
- `vote` — `{type, nickname, step_order}` (participant votes for next game)
- `start_session`, `next_step`, `end_session` — host controls
- `navigate_direct` — `{type, game_key, room_code}`

**Server → Client:**
- `state` — full session state: participants, steps, current index
- `lobby_update` — participant list changed
- `navigate` — redirect participants to a game step
- `vote_update` — `{votes: [{step_order, game_key, title, count}, ...]}`
- `session_started`, `session_ended`

#### Game consumer pattern (`ws/<game>/<room_code>/`)

Host messages: `admin_start_quiz`, `admin_send_question` (`{question_id, custom_time_limit}`), `admin_end_question`, `admin_end_quiz`.
Participant messages: `participant_join` (`{participant_name, hub_session}`), `participant_submit_answer` (`{answer, time_taken, hub_session}`).
Broadcast: `question_started`, `question_ended` (with `correct_answer`), `quiz_ended` / `game_ended` (with `final_scores`).

When a game ends, the consumer sends a `hub_mirror_event('game_ended', {...})` to notify the hub to advance to the next step.

### Hub API endpoints

All at `/hub/api/`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `session/<code>/leaderboard/` | GET | Session leaderboard |
| `session/<code>/add-step/` | POST | Add game step: `{game_key, question_ids[]}` |
| `session/<code>/delete-step/<step_id>/` | POST | Remove a game step and renumber |
| `session/<code>/reorder-steps/` | POST | Reorder steps: `{order: [step_id, ...]}` |
| `session/<code>/vote/` | POST | Submit vote: `{nickname, step_order}` |
| `session/<code>/votes/` | GET | Current vote counts |
| `games/<game_key>/questions/` | GET | Available questions for a game type |
| `participant/score/` | POST | Manually adjust participant score |

### Data model pattern

Every game follows the same structure:
- `<Game>Quiz` / `<Game>Game` — the game instance (has `room_code`, `status`, `selected_questions` M2M, `creator`)
- `<Game>Question` — the question bank (global, not scoped to a quiz instance); each participant record stores `hub_session_code` to link to a hub session
- `<Game>Participant` — join record per player per game
- `<Game>Answer` — individual answers
- `<Game>Bundle` — named grouping of questions, used in the admin dashboard for bulk selection

Questions are assigned to a quiz via `selected_questions` (ManyToMany). When a game step is created from the Session Monitor, the host selects questions which are stored this way.

**Exception — `clue_rush`**: Questions are `ClueQuestion`, each with multiple `Clue` child objects (progressive hints revealed over time). There is no `ClueBundle`; question selection uses `selected_questions` M2M directly on `ClueRushGame`.

**`SyncBase`**: Most game and hub models inherit from `games_website.models.SyncBase`, which adds `synced: BooleanField` and `updated_at: DateTimeField(auto_now=True)`. These fields are used by `games_website/services.py` (`sync_all_models_to_supabase`, `restore_all_models_from_supabase`) to push/pull data to/from the production Supabase PostgreSQL database.

**Hub-specific models:**
- `HubSession` — has `code` (unique), `name`, `is_active`, `current_step_index`, `games_weight` (float, scoring weight), `scoreboard_visible`
- `HubParticipant` — one per player per session; `nickname`, `score_adjustment` (host-editable)
- `HubGameStep` — has `unique_together = ('session', 'order')`. When computing the next order value, always use `is None` check: `0 if max_order is None else max_order + 1` — Python's `or` treats `0` as falsy. Valid `game_key` choices: `quiz`, `assign`, `estimation`, `where`, `who`, `who_that`, `blackjack`, `sorting_ladder` (note: `clue_rush` is missing from `GAME_CHOICES` on the model but is handled in `views.py`).
- `GameVote` — one vote per participant per session (`unique_together = ('session', 'participant_nickname')`), pointing to a `HubGameStep`

**Leaderboard aggregation** (`views.py:get_leaderboard_data`): For each game step, fetches participants with matching `hub_session_code`. The participant with the highest score per step earns 1 hub point; ties share it. The host can apply manual adjustments via `HubParticipant.score_adjustment`.

### Adding a new game type

When adding a new game to the hub flow, these four places must all be updated in sync:

1. **`games_hub/views.py:auto_create_game_quiz`** — factory that creates the game instance and returns its `room_code`
2. **`games_hub/views.py:GAME_QUESTION_MAP`** (inside `create_session`) — maps game key to `(GameModel, QuestionModel, post_field_name)` for question assignment during session creation
3. **`games_hub/views.py:_assign_questions_to_quiz`** — maps game key to `(GameModel, QuestionModel)` for question assignment when adding a step to a running session
4. **`templates/hub/create_session.html:GAME_SECTION_MAP`** — maps game key to the HTML section ID for question selection in the creation wizard

> **Known gap**: `clue_rush` is handled by `auto_create_game_quiz` and `_assign_questions_to_quiz` but is missing from `GAME_QUESTION_MAP` in `create_session`, from `GAME_SECTION_MAP` in the template, and from `HubGameStep.GAME_CHOICES`. It can only be added via the session monitor's "Add Game" button, not during initial session creation.

### Room codes

Room codes identify individual game instances (4-digit numeric string, unique per game model). Participants do not interact with room codes directly in hub sessions — the hub injects them automatically via WebSocket `navigate` messages. Room codes are only user-visible in the standalone direct-join flow (`/quiz/join/` etc.) where no hub session is involved. Do not display room codes in hub-facing or result-page UI.

### Templates

- `templates/admin_dashboard/` — host-facing pages (base layout, game monitors, management pages)
- `templates/hub/` — hub pages (lobby, leaderboard, session monitor, session creation wizard)
- `templates/<game>/play.html` — participant game view per game type

The admin dashboard uses its own `base.html` with a sidebar layout (Bootstrap 5 + Lucide icons). The session creation wizard in `create_session.html` is a two-step form: step 1 selects games, step 2 selects questions per game. The form uses `novalidate` and relies on JS validation to avoid browser focus errors on hidden required fields.

### Key dependencies

- `rapidfuzz` — fuzzy text matching in answer evaluation (e.g. `clue_rush`)
- `Pillow` — image handling for `who_is_that` and `where_is_this` (media uploads stored in `media/`)
- `playwright` — used in `admin_dashboard/tests.py` for browser-based JS tests (search/filter in `ManageGamesBrowserTest`)

### Configuration

Secrets are loaded from `secrets.env` via `python-dotenv`. The file is git-ignored. Required variables: `DJANGO_SECRET_KEY`, and optionally Supabase DB credentials for production.

Database defaults to SQLite (`db.sqlite3`). A secondary `supabase` database alias is available for production sync via `games_website/services.py`.

Media uploads (images for `who_is_that`, `where_is_this`) are stored in `media/` and served at `/media/` in development only (`DEBUG=True`).

**Authentication**: Admin dashboard views require `is_staff` or `is_superuser`. Use the `@admin_required` decorator (defined in `admin_dashboard/views.py`) or `@login_required`. The login page is at `/admin-dashboard/login/`; after login, the default redirect is `/`.

### Admin dashboard — game creation endpoints

Each game type has **two** create endpoints:

- **Quick-create** (`/admin-dashboard/<type>/create/`) — ignores the request body, always uses a hardcoded default title (e.g. `"Quick Quiz"`, `"Estimation Quiz"`).
- **Custom-create** (`/admin-dashboard/<type>/create-custom/`) — reads `{title, question_ids}` from a JSON body and saves the provided title.

When writing tests or scripts that need a specific title, always use the custom-create endpoint. The generic delete endpoint at `/admin-dashboard/games/delete/` (POST) accepts `{game_type, game_id}` and works for all types.

### Tests

Automated tests live in `admin_dashboard/tests.py` and cover login, game creation/deletion for all 9 types, search/filter UI (Playwright), and session creation. The seed script (`seed_test_data.py`) prefixes all generated objects with `[seed]` so they can be bulk-deleted with `--clear`.

**Django 6.0 + Python 3.14**: `LiveServerTestCase` runs test methods inside an asyncio event loop, which causes `SynchronousOnlyOperation` on any synchronous DB call — including Django's own `flush` during teardown. Fix: set `os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"` at the top of the test module (before Django setup). This is already done in `admin_dashboard/tests.py`; apply the same pattern to any future `LiveServerTestCase` subclass.
