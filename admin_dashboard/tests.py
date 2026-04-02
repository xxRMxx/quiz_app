"""
Automatisierte Tests für das Admin-Dashboard.

Abgedeckte Bereiche:
  - Login
  - Manage Games: Spiel anlegen (alle Typen), 2 löschen, Suche & Filter (Playwright), Zurück-Link
  - Sessions: Zurück-Link, neue Session mit je einem Spiel pro Typ
"""

# Django 6 / Python 3.14: LiveServerTestCase läuft intern in einem Event-Loop.
# Ohne dieses Flag schlägt jede synchrone DB-Operation (inkl. Django-internes
# flush) mit SynchronousOnlyOperation fehl.
import os
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

import json
import random
import string

from django.contrib.auth.models import User
from django.test import Client, LiveServerTestCase, TestCase
from django.urls import reverse

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

GAME_CREATE_URLS = {
    "quiz":           "admin_dashboard:create_quiz",
    "estimation":     "admin_dashboard:create_estimation_quiz",
    "assign":         "admin_dashboard:create_assign_quiz",
    "where":          "admin_dashboard:create_where_quiz",
    "who":            "admin_dashboard:create_who_quiz",
    "who_that":       "admin_dashboard:create_who_that_quiz",
    "blackjack":      "admin_dashboard:create_blackjack_quiz",
    "clue_rush":      "admin_dashboard:create_clue_rush_game",
    "sorting_ladder": "admin_dashboard:create_sorting_ladder_game",
}

# Custom-Create-Endpunkte akzeptieren einen "title"-Parameter im JSON-Body.
# Die Quick-Create-Endpunkte oben ignorieren den Titel (hardcoded).
GAME_CUSTOM_CREATE_URLS = {
    "quiz":           "admin_dashboard:create_custom_quiz",
    "estimation":     "admin_dashboard:create_estimation_custom_quiz",
    "assign":         "admin_dashboard:create_assign_custom_quiz",
    "where":          "admin_dashboard:create_where_custom_quiz",
    "who":            "admin_dashboard:create_who_custom_quiz",
    "who_that":       "admin_dashboard:create_who_that_custom_quiz",
    "blackjack":      "admin_dashboard:create_black_jack_custom_quiz",
    "clue_rush":      "admin_dashboard:create_clue_rush_custom_game",
    "sorting_ladder": "admin_dashboard:create_sorting_ladder_custom_game",
}

GAME_TYPE_DISPLAY = {
    "quiz":           "Quick Quiz",
    "estimation":     "Estimation",
    "assign":         "Assign",
    "where":          "Where Is This?",
    "who":            "Who Is Lying?",
    "who_that":       "Who Is That?",
    "blackjack":      "Black Jack Quiz",
    "clue_rush":      "Clue Rush",
    "sorting_ladder": "Sorting Ladder",
}


def rand_str(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def make_admin(username=None, password="testpass123"):
    username = username or f"admin_{rand_str()}"
    return User.objects.create_superuser(username=username, password=password, email="")


# ---------------------------------------------------------------------------
# 1. Login-Tests
# ---------------------------------------------------------------------------

class LoginTest(TestCase):

    def setUp(self):
        self.password = "securePass99"
        self.user = make_admin(username="testadmin", password=self.password)
        self.login_url = reverse("admin_dashboard:login")
        self.home_url = reverse("admin_dashboard:home")

    def test_login_valid_credentials(self):
        """Korrektes Login leitet zum Dashboard weiter."""
        resp = self.client.post(self.login_url, {
            "username": self.user.username,
            "password": self.password,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.redirect_chain[-1][0], [self.home_url, "/"])

    def test_login_invalid_credentials(self):
        """Falsches Passwort führt NICHT zum Dashboard (bleibt auf Login-Seite)."""
        resp = self.client.post(self.login_url, {
            "username": self.user.username,
            "password": "wrongpassword",
        }, follow=True)
        # Bleibt auf Login-Seite (kein Redirect zum Dashboard)
        final_url = resp.redirect_chain[-1][0] if resp.redirect_chain else resp.wsgi_request.path
        self.assertNotIn("dashboard", final_url.replace("admin-dashboard/login", ""))

    def test_login_page_accessible(self):
        """Login-Seite ist ohne Authentifizierung erreichbar."""
        resp = self.client.get(self.login_url)
        self.assertEqual(resp.status_code, 200)

    def test_logout(self):
        """Logout beendet die Session."""
        self.client.force_login(self.user)
        resp = self.client.post(reverse("admin_dashboard:logout"), follow=True)
        self.assertEqual(resp.status_code, 200)
        # Nach Logout: Dashboard nicht mehr erreichbar ohne Redirect zu Login
        resp2 = self.client.get(self.home_url)
        self.assertNotEqual(resp2.status_code, 200)  # Redirect oder 403

    def test_already_logged_in_redirects(self):
        """Eingeloggter Admin wird vom Login auf Dashboard weitergeleitet."""
        self.client.force_login(self.user)
        resp = self.client.get(self.login_url)
        self.assertIn(resp.status_code, [301, 302])


# ---------------------------------------------------------------------------
# 2. Manage-Games-Tests (Backend / API)
# ---------------------------------------------------------------------------

class ManageGamesApiTest(TestCase):
    """Testet das Erstellen und Löschen von Spielen via AJAX-Endpunkte."""

    def setUp(self):
        self.user = make_admin()
        self.client.force_login(self.user)

    # -- Spiel anlegen (je Typ) -----------------------------------------------

    def _create_game(self, game_key):
        url = reverse(GAME_CREATE_URLS[game_key])
        resp = self.client.post(
            url,
            data=json.dumps({"title": f"Test {GAME_TYPE_DISPLAY[game_key]} {rand_str(4)}"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, f"Erstellen fehlgeschlagen für '{game_key}': {resp.content}")
        data = resp.json()
        self.assertTrue(data.get("success"), f"Kein success=True für '{game_key}': {data}")
        self.assertIn("room_code", data, f"Kein room_code in Antwort für '{game_key}'")
        return data

    def test_create_quiz_game(self):
        self._create_game("quiz")

    def test_create_estimation_game(self):
        self._create_game("estimation")

    def test_create_assign_game(self):
        self._create_game("assign")

    def test_create_where_game(self):
        self._create_game("where")

    def test_create_who_game(self):
        self._create_game("who")

    def test_create_who_that_game(self):
        self._create_game("who_that")

    def test_create_blackjack_game(self):
        self._create_game("blackjack")

    def test_create_clue_rush_game(self):
        self._create_game("clue_rush")

    def test_create_sorting_ladder_game(self):
        self._create_game("sorting_ladder")

    # -- Zwei Spiele löschen --------------------------------------------------

    def test_delete_two_games(self):
        """Legt je einen Quiz und einen Estimation-Eintrag an und löscht beide."""
        quiz_data = self._create_game("quiz")
        estimation_data = self._create_game("estimation")

        delete_url = reverse("admin_dashboard:delete_game_instance")

        for game_type, data in [("quiz", quiz_data), ("estimation", estimation_data)]:
            game_id = data.get("quiz_id") or data.get("game_id")
            resp = self.client.post(
                delete_url,
                data=json.dumps({"game_type": game_type, "game_id": game_id}),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200, f"Löschen fehlgeschlagen für '{game_type}'")
            result = resp.json()
            self.assertTrue(result.get("success"), f"success != True beim Löschen von '{game_type}': {result}")

    # -- Manage-Games-Seite ladbar --------------------------------------------

    def test_manage_games_page_loads(self):
        """Die Übersichtsseite aller Spiele lädt ohne Fehler."""
        resp = self.client.get(reverse("admin_dashboard:manage_games"))
        self.assertEqual(resp.status_code, 200)
        # Such-Input und Typ-Filter müssen im HTML vorhanden sein
        content = resp.content.decode()
        self.assertIn("gameSearchInput", content)
        self.assertIn("gameTypeFilter", content)

    def test_manage_games_shows_created_game(self):
        """Ein neu erstelltes Spiel erscheint auf der Übersichtsseite."""
        title = f"Suchtest_{rand_str(6)}"
        # Muss Custom-Create verwenden, da Quick-Create den Titel ignoriert
        resp = self.client.post(
            reverse(GAME_CUSTOM_CREATE_URLS["quiz"]),
            data=json.dumps({"title": title}),
            content_type="application/json",
        )
        self.assertTrue(resp.json().get("success"))

        page = self.client.get(reverse("admin_dashboard:manage_games"))
        self.assertContains(page, title)

    # -- Zurück zum Hauptmenü -------------------------------------------------

    def test_back_to_main_menu_link_present(self):
        """Das Manage-Games-Template enthält einen Link zurück zum Dashboard."""
        resp = self.client.get(reverse("admin_dashboard:manage_games"))
        self.assertEqual(resp.status_code, 200)
        home_url = reverse("admin_dashboard:home")
        self.assertContains(resp, home_url)


# ---------------------------------------------------------------------------
# 3. Sessions-Tests (Backend)
# ---------------------------------------------------------------------------

class SessionsTest(TestCase):

    def setUp(self):
        self.user = make_admin()
        self.client.force_login(self.user)
        self.create_session_url = reverse("games_hub:create_session")

    def _create_game_room(self, game_key):
        """Legt ein Spiel an und gibt dessen room_code zurück."""
        url = reverse(GAME_CREATE_URLS[game_key])
        resp = self.client.post(
            url,
            data=json.dumps({"title": f"Session-Test {GAME_TYPE_DISPLAY[game_key]}"}),
            content_type="application/json",
        )
        data = resp.json()
        self.assertTrue(data.get("success"), f"Spiel-Erstellung fehlgeschlagen für {game_key}: {data}")
        return data["room_code"]

    # -- Zurück-Link auf Sessions-Seite ---------------------------------------

    def test_sessions_overview_back_link(self):
        """Die Sessions-Übersicht enthält einen Link zum Dashboard (Hauptmenü)."""
        resp = self.client.get(reverse("admin_dashboard:sessions_overview"))
        self.assertEqual(resp.status_code, 200)
        home_url = reverse("admin_dashboard:home")
        self.assertContains(resp, home_url)

    def test_create_session_page_loads(self):
        """Die Seite zum Erstellen einer Session lädt ohne Fehler."""
        resp = self.client.get(self.create_session_url)
        self.assertEqual(resp.status_code, 200)

    # -- Neue Session mit je einem Spiel pro Typ ------------------------------

    def test_create_session_with_all_game_types(self):
        """Erstellt eine Session mit einem Spiel pro Spieltyp und zufälligem Namen."""
        session_name = f"Test-Session-{rand_str(6)}"

        # Für jeden Spieltyp ein Spiel anlegen
        games_order = []
        for game_key in GAME_CREATE_URLS:
            room_code = self._create_game_room(game_key)
            games_order.append({
                "game_key": game_key,
                "room_code": room_code,
                "title": GAME_TYPE_DISPLAY[game_key],
            })

        resp = self.client.post(
            self.create_session_url,
            data={
                "name": session_name,
                "games_order": json.dumps(games_order),
            },
            follow=True,
        )

        # Erfolg: Redirect zum Monitor der neu erstellten Session
        self.assertEqual(resp.status_code, 200)
        final_url = resp.redirect_chain[-1][0] if resp.redirect_chain else ""
        self.assertIn("/hub/monitor/", final_url, f"Kein Redirect zum Monitor: {resp.redirect_chain}")

        # Session wurde in DB angelegt
        from games_hub.models import HubSession, HubGameStep
        session = HubSession.objects.get(name=session_name)
        self.assertEqual(session.steps.count(), len(GAME_CREATE_URLS))

    def test_create_session_random_name(self):
        """Session-Name ist frei wählbar (zufälliger String)."""
        random_name = rand_str(12)
        room_code = self._create_game_room("quiz")

        resp = self.client.post(
            self.create_session_url,
            data={
                "name": random_name,
                "games_order": json.dumps([
                    {"game_key": "quiz", "room_code": room_code, "title": "Quick Quiz"}
                ]),
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        from games_hub.models import HubSession
        self.assertTrue(HubSession.objects.filter(name=random_name).exists())

    def test_create_session_back_link(self):
        """Die Session-Erstellungsseite enthält einen Link zum Hauptmenü."""
        resp = self.client.get(self.create_session_url)
        self.assertEqual(resp.status_code, 200)
        home_url = reverse("admin_dashboard:home")
        self.assertContains(resp, home_url)


# ---------------------------------------------------------------------------
# 4. Browser-Tests mit Playwright (Suche & Filter in Manage Games)
# ---------------------------------------------------------------------------

class ManageGamesBrowserTest(LiveServerTestCase):
    """
    Testet clientseitige Funktionen (Suche, Typ-Filter) mit Playwright.
    Voraussetzung: playwright + Chromium installiert.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            from playwright.sync_api import sync_playwright
            cls._pw = sync_playwright().start()
            cls._browser = cls._pw.chromium.launch(headless=True)
            cls._playwright_available = True
        except Exception:
            cls._playwright_available = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_playwright_available", False):
            cls._browser.close()
            cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        if not self._playwright_available:
            self.skipTest("Playwright/Chromium nicht verfügbar")
        self.password = "testpass123"
        self.admin = make_admin(username=f"btest_{rand_str()}", password=self.password)
        self.context = self._browser.new_context()
        self.page = self.context.new_page()
        self._login()
        self._create_test_games()

    def tearDown(self):
        self.page.close()
        self.context.close()

    def _login(self):
        """Loggt den Admin-User via Browser ein."""
        self.page.goto(f"{self.live_server_url}{reverse('admin_dashboard:login')}")
        self.page.fill("input[name='username']", self.admin.username)
        self.page.fill("input[name='password']", self.password)
        self.page.click("button[type='submit']")
        self.page.wait_for_url(f"**{reverse('admin_dashboard:home')}**", timeout=5000)

    def _create_test_games(self):
        """Legt Testspiele mit Custom-Titeln an (verwendet Custom-Create-Endpunkte)."""
        from django.test import Client as DjangoClient
        c = DjangoClient()
        c.force_login(self.admin)
        self._test_titles = {}
        for game_key, url_name in GAME_CUSTOM_CREATE_URLS.items():
            title = f"Suchspiel {GAME_TYPE_DISPLAY[game_key]} {rand_str(4)}"
            resp = c.post(
                reverse(url_name),
                data=json.dumps({"title": title}),
                content_type="application/json",
            )
            if resp.status_code == 200 and resp.json().get("success"):
                self._test_titles[game_key] = title

    def test_search_by_name_filters_rows(self):
        """Tippen in das Suchfeld blendet nicht-passende Spiele aus."""
        self.page.goto(f"{self.live_server_url}{reverse('admin_dashboard:manage_games')}")
        self.page.wait_for_selector("#gameSearchInput")

        # Alle Testspiele haben "Suchspiel" im Titel — gemeinsamer Prefix der nur
        # auf unsere Testdaten passt, nicht auf Default-Titel wie "Quick Quiz".
        search_term = "Suchspiel"
        self.page.fill("#gameSearchInput", search_term)

        # Kurz warten, damit JS-Filter läuft
        self.page.wait_for_timeout(300)

        # Alle sichtbaren Zeilen lesen
        rows = self.page.locator("tbody tr[onclick]")
        visible_count = 0
        for i in range(rows.count()):
            row = rows.nth(i)
            if row.is_visible():
                visible_count += 1
                name_text = row.locator("td:nth-child(2)").text_content().lower()
                self.assertIn("suchspiel", name_text,
                              f"Sichtbare Zeile passt nicht zum Suchbegriff: {name_text!r}")
        self.assertGreaterEqual(visible_count, 1, "Keine Treffer nach Suche")

    def test_filter_by_game_type(self):
        """Der Typ-Filter blendet nur Spiele des gewählten Typs ein."""
        self.page.goto(f"{self.live_server_url}{reverse('admin_dashboard:manage_games')}")
        self.page.wait_for_selector("#gameTypeFilter")

        # Auf "Quick Quiz" filtern
        self.page.select_option("#gameTypeFilter", "quick quiz")
        self.page.wait_for_timeout(300)

        rows = self.page.locator("tbody tr[onclick]")
        for i in range(rows.count()):
            row = rows.nth(i)
            if row.is_visible():
                type_text = row.locator("td:nth-child(3)").text_content().lower()
                self.assertIn("quick quiz", type_text,
                              f"Sichtbare Zeile hat falschen Typ: {type_text!r}")

    def test_filter_reset_shows_all(self):
        """Zurücksetzen des Filters zeigt wieder alle Zeilen."""
        self.page.goto(f"{self.live_server_url}{reverse('admin_dashboard:manage_games')}")
        self.page.wait_for_selector("#gameTypeFilter")

        total_before = self.page.locator("tbody tr[onclick]").count()

        self.page.select_option("#gameTypeFilter", "quick quiz")
        self.page.wait_for_timeout(200)

        self.page.select_option("#gameTypeFilter", "")
        self.page.wait_for_timeout(200)

        visible_after = sum(
            1 for i in range(self.page.locator("tbody tr[onclick]").count())
            if self.page.locator("tbody tr[onclick]").nth(i).is_visible()
        )
        self.assertEqual(visible_after, total_before)

    def test_back_to_main_menu_click(self):
        """Klick auf Logo/Hauptmenü-Link navigiert zurück zum Dashboard."""
        self.page.goto(f"{self.live_server_url}{reverse('admin_dashboard:manage_games')}")
        home_url = reverse("admin_dashboard:home")
        # Link mit href zum Dashboard anklicken
        self.page.click(f"a[href='{home_url}']")
        self.page.wait_for_url(f"**{home_url}**", timeout=5000)
        self.assertIn(home_url, self.page.url)

    def test_sessions_back_to_main_menu_click(self):
        """Auf der Sessions-Seite navigiert der Hauptmenü-Link korrekt."""
        self.page.goto(f"{self.live_server_url}{reverse('admin_dashboard:sessions_overview')}")
        home_url = reverse("admin_dashboard:home")
        self.page.click(f"a[href='{home_url}']")
        self.page.wait_for_url(f"**{home_url}**", timeout=5000)
        self.assertIn(home_url, self.page.url)
