REQUIREMENTS (tested on Linux)
	* Python3.x
	* python3-venv (sudo apt install libpython3-dev python3-venv )
	* pip3
	* venv
	* daphne server (sudo apt install daphne)
	* redis-server (sudo apt install redis-server)
	* optional: redis-tools (sudo apt install redis-tools)

INSTALLATION
	* create virtual environment: python3 -m venv <virtual_environment>
	* activate venv: source <your_venv>/bin/activate
	* pip3 install -r requirements.txt

CREATE SUPERUSER IN DJANGO
	* in venv: python3 manage.py createsuperuser
	* export DJANGO_SETTINGS_MODULE=quiz_project.settings
	* start daphne server: daphne -p 8000 quiz_project.asgi:application (if redis-server not yet running: sudo service redis-server (re-)start)

PAGES
	* admin section: localhost:8000/admin
	* admin dashboard: localhost:8000/my-admin/<session_id>
	* landing page for participants site: localhost:8000
	* connect to existing session: localhost:8000/quiz/session-code>/<participant-id> <-- you can check every session and participant in admin panel
