Server starten
	python manage.py runserver

Admin-Page
	localhost:8000/admin

Quiz-Session
	localhost:8000/quiz/<session-code>
	--> der Session-Code ist über das Admin-Dashboard einsehbar

Admin-Dashboard (zum Steuern vom Quiz)
	localhost:8000/admin-dashboard/<session-code>

Ablauf:
1. Admin startet eine Session (legt einen Session-Code fest)
2. Teilnehmer loggen sich über Session-Code ein (z.B. auf Startpage mit 1234)
3. Admin wählt über Admin-Dashboard eine Frage aus Dropdown-Menü aus & sendet die Frage
4. Teilnehmer aktualisiert Seite und sieht nächste Frage
5. Teilnehmer wählt Antwort aus und schickt Antwort ab
6. Admin aktualisiert Seite und sieht Antworten der Teilnehmer
7. Steps von vorne
