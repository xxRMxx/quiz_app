# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run development server (with WebSocket support)
daphne -b 0.0.0.0 -p 8000 games_website.asgi:application

# Run migrations
python manage.py migrate

# Run all tests
python manage.py test

# Run tests for a single app
python manage.py test QuizGame
python manage.py test Assign

# Seed test data (creates admin/admin123, 18 game instances, 1 HubSession)
python seed_test_data.py
python seed_test_data.py --clear   # clear and recreate

# Database snapshots
bash db_save_snapshot.sh
bash db_restore_test.sh

# Sync with Supabase (production DB)
python manage.py sync_to_supabase
python manage.py restore_from_supabase
```

## Architecture

### Apps
There are 11 Django apps. Each game app is self-contained:

| App | Game |
|-----|------|
| `QuizGame` | Multiple-choice / True-False / Short-answer |
| `Estimation` | Numerical estimation with tolerance scoring |
| `Assign` | Drag-and-drop item matching (round-based) |
| `who_is_lying` | Identify the liar in a group |
| `where_is_this` | Location/landmark image identification |
| `who_is_that` | Face identification from photos |
| `black_jack_quiz` | Numerical trivia with BlackJack-style mechanics |
| `clue_rush` | Fast-paced clue-based trivia |
| `sorting_ladder` | Sort items in the correct order |
| `games_hub` | Multi-game session orchestrator |
| `admin_dashboard` | Central management UI for all games (290+ routes) |

### Standard game app pattern
Every game app follows the same structure:
- `<Game>Quiz`/`<Game>Game` — game instance with `status`, `room_code`, `current_question`, `question_start_time`
- `<Game>Participant` — player with `total_score` and `hub_session_code` (for multi-game hub linking)
- `<Game>Question` — type-specific fields
- `<Game>Answer`/`<Game>Response` — recorded submissions (written at question end)
- `<Game>Bundle` — reusable question collections (templates for creating sessions)
- `<Game>Session` — live session state (separate from the quiz instance itself)
- `AsyncWebsocketConsumer` — real-time updates via Channels

All models inherit from `SyncBase` (`games_website/models.py`), which adds `synced: bool` and `updated_at` for Supabase sync tracking.

### Hub session orchestration (`games_hub`)
`HubSession` sequences multiple games into one event:
- `HubGameStep` links a `HubSession` to an individual game room (`game_key` + `room_code`)
- Participants join via the hub lobby (`/hub/lobby/<session_code>/`) and are forwarded to each game in sequence
- `Participant.hub_session_code` on every game model ties responses back to the hub session
- When a game ends, its consumer calls `hub_mirror_event('quiz_ended', {...})` which sends a `hub_event` message to the hub's channel group (`hub_<session_code>`) so the hub can auto-advance to the next step

### Real-time (WebSockets)
- ASGI via Daphne + Django Channels
- Each game defines `websocket_urlpatterns` in its `routing.py`; all are aggregated in `games_website/asgi.py`
- WS URL pattern: `ws/<game_type>/<room_code>/`
- Channel layer: `InMemoryChannelLayer` for dev (`DEBUG=True`), Redis (`127.0.0.1:6379`) for production
- **Consumer class-level state** (`_round_submissions`, `_auto_advancing`, `_participant_channels` dicts/sets on the class) is in-process memory — not shared across multiple workers/processes

### Assign round-based mode
`Assign` sends a question's left items one at a time, each as a separate "round":
- `AssignSession.current_round_index` (DB) tracks which round is active globally
- Per round the client receives one left item and the remaining right items (already-matched ones are filtered out)
- Right items are shuffled deterministically via `AssignQuestion.get_randomized_items(room_code)` — seed = `hash(f"{question_id}_{room_code}")` — ensuring all clients see the same shuffle
- Two-phase WS protocol per round:
  1. `participant_check_round` → server replies `round_checked` (is_correct, no DB write) and tracks submission for auto-advance
  2. `participant_submit_answer` → server writes `AssignAnswer` to DB (sent at question end when all rounds complete)
- Auto-advance triggers when all connected participants have submitted for a round (2 s delay, then `handle_admin_next_round`)

### Admin Dashboard
All game management runs through `admin_dashboard/`. Requires admin login at `/admin-dashboard/login/` (staff or superuser). The management pages use vanilla JS with `fetch()` against 290+ REST-style endpoints in `admin_dashboard/urls.py`. Live monitors poll endpoints like `/api/<game>/<room_code>/stats/`.

`manage_games.html` is the primary template used for question/topic management across all game types — changes to question editing UI go here.

### Frontend
Django templates + Bootstrap 5.3.2 + Lucide Icons (CDN) + vanilla JS. No frontend build step. Templates live in the top-level `templates/` directory (not per-app). After dynamically inserting HTML containing `data-lucide` attributes, always call `lucide.createIcons()`.

### Database
- **Dev:** SQLite (`db.sqlite3`)
- **Test:** File-based SQLite (`test_db.sqlite3`) — required because `ChannelsLiveServerTestCase` spawns a real ASGI server in a thread that cannot share an in-memory SQLite connection
- **Production:** PostgreSQL via Supabase (credentials from `secrets.env` or env vars: `SUPABASE_DB_NAME`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD`, `SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`)
- Bidirectional sync via `games_website/services.py`; models with `synced=False` are pushed on the next sync run

### Static files
`games_website/asgi.py` wraps the Django ASGI app with `ASGIStaticFilesHandler` so that Daphne serves static files in development. Do not use `runserver` — it does not handle WebSockets.

### Room codes
Auto-generated 4-digit numeric codes, unique per game instance (`generate_unique_room_code()` on each Quiz model). `who_is_lying` uses hash-based deterministic shuffling for consistent question order across clients.
