# UI-Modernisierung: Design Spec
**Datum:** 2026-04-07  
**Branch:** `ui_ux`  
**Scope:** Alle Templates (~55) — Admin-Dashboard + Spieler-Seiten

---

## Ziel

Das bestehende UI soll moderner wirken und intuitiver zu bedienen sein. Kernprinzip: **ein zentrales CSS-System** sorgt für einen konsistenten Look über alle Seiten — einheitliche Buttons, Inputs, Cards, Badges und Tabellen überall.

---

## Design-Richtung: Refined Dark

Durchgehend dunkles Theme, das den bestehenden Spieler-Seiten ähnelt und ein kohärentes Gesamtbild ergibt. Kein Bruch mehr zwischen Admin (hell) und Spieler (dunkel).

**Fonts:**
- `Syne` (700/800) — Headings, Section-Labels, Navbar-Logo
- `DM Sans` (400/500/600) — Body, Buttons, Inputs, UI-Text

---

## Design Tokens

```css
/* Hintergründe */
--bg:           #0a0e1a;   /* Seiten-Hintergrund */
--surface:      #0f1628;   /* Cards, Panels */
--surface-2:    #161e35;   /* Table-Header, Hover-States */

/* Borders */
--border:       rgba(255,255,255,0.08);
--border-focus: #a78bfa;

/* Farben */
--primary:      #7c3aed;
--primary-h:    #6d28d9;   /* Hover */
--primary-lite: rgba(124,58,237,0.15);
--accent:       #a78bfa;

/* Status */
--success:      #34d399;
--warning:      #fbbf24;
--danger:       #f87171;

/* Text (alle WCAG AA konform) */
--text:         #e2e8f0;   /* 14.7:1 — Primärtext */
--text-muted:   #94a3b8;   /* 6.1:1  — Sekundärtext */
--text-faint:   #64748b;   /* 3.4:1  — nur Tabellenköpfe/dekorativ (Großschrift) */

/* Spacing & Form */
--radius-sm:    8px;
--radius:       12px;
--radius-pill:  999px;
--shadow:       0 4px 16px rgba(0,0,0,0.4);
--transition:   150ms ease-in-out;
```

---

## Komponenten

### Buttons

Vier Varianten, einheitliche Basis:

| Klasse | Verwendung |
|--------|------------|
| `.btn-primary` | Hauptaktion (Neu, Speichern, Beitreten) |
| `.btn-ghost` | Sekundäraktion (Zurück, Abbrechen) |
| `.btn-danger` | Destruktiv (End, Delete) |
| `.btn-success` | Bestätigung (Speichern, Erstellen) |

Größen: `.btn-sm` (min. 44px Höhe), Standard, `.btn-lg`  
Icon-Buttons: `.btn-icon` mit `aria-label` Pflicht  
Alle Buttons: min. 44×44px Touch-Target (WCAG 2.5.5)

### Eingabefelder

Einheitliche `.form-control` Klasse für alle `<input>`, `<select>`, `<textarea>`:
- Normal: `rgba(255,255,255,0.04)` Background, `var(--border)` Border
- Hover: leicht heller
- Focus: `var(--border-focus)` Border + Glow-Shadow mit `:focus-visible`
- Error: `var(--danger)` Border + Pflicht-Hinweistext (nie nur Farbe)
- Code-Felder: `letter-spacing: 4px`, zentriert, Accent-Farbe

Alle Felder haben sichtbare `<label>` mit Klasse `.form-label`.

### Cards

`.card` mit optionalem `.card-header` und `.card-body`:
- Background: `var(--surface)`
- Border: `var(--border)`
- Hover: `border-color` → `rgba(167,139,250,0.25)` + `translateY(-2px)`

### Badges / Status

`.badge` mit Varianten `.badge-live`, `.badge-planned`, `.badge-ended`, `.badge-primary`  
**Pflicht:** immer Icon + Text (nie nur Farbe):
- LIVE: `●` Punkt + Text
- GEPLANT: `⏱` + Text  
- BEENDET: `■` + Text

### Tabellen

`.data-table` in einem `.table-wrap` Container:
- Thead: `var(--surface-2)`, Syne-Font, uppercase, `var(--text-faint)`
- Tbody-Rows: Hover mit `rgba(255,255,255,0.02)`
- Code-Chips: `.code-chip` — violetter Akzent, Monospace

---

## Dateistruktur

```
static/
  theme.css        ← wird zur Dark-Theme-Basis (Admin + geteilt)
  player.css       ← neu: geteilt für alle Spieler-Seiten

templates/
  admin_dashboard/
    base.html      ← lädt Syne + DM Sans, theme.css
  includes/
    player_head.html  ← neu: <head>-Fragment für Spieler-Templates
                         (Fonts + player.css, kein base.html nötig)
```

---

## Migrationsplan

**Phase 1 — CSS-System** (kein Template-Touch nötig)
1. `theme.css` → Dark-Token-Variablen + alle Komponenten-Klassen
2. `base.html` → Fonts laden, Bootstrap-Overrides

**Phase 2 — Admin-Templates** (erben via base.html)
3. `landing.html` — Neues Grid-Design
4. `index.html` (Sessions) — Tabellen auf `.data-table` umstellen
5. `create_session.html` — Formulare auf `.form-control` umstellen
6. Alle `*_management.html` und `*_monitor.html` — Inline-Styles bereinigen

**Phase 3 — Spieler-Templates**
7. `player.css` erstellen
8. `player_head.html` Include-Fragment erstellen
9. `hub/join_session.html` + `hub/lobby.html` — auf neue Klassen umstellen
10. Alle `*/join.html`, `*/play.html`, `*/result.html` — Inline-Styles ersetzen
11. Leaderboard-Seiten

---

## Accessibility (WCAG 2.1 AA)

- Alle Body-Texte: Kontrast ≥ 4.5:1
- Fokus-Ringe: 3px solid `var(--accent)` + Offset, via `:focus-visible`
- Touch-Targets: min. 44×44px für alle interaktiven Elemente
- Status immer mit Icon + Text (nicht nur Farbe)
- Fehler-States: Hinweistext, nicht nur rote Border
- `aria-label` Pflicht auf allen Icon-Buttons
- Bestehende Accessibility-Widget (`includes/accessibility_widget.html`) bleibt erhalten
- High-Contrast-Overrides in `base.html` werden auf neues System portiert

---

## Was nicht geändert wird

- JavaScript-Logik (WebSocket-Handler, Fetch-Calls, etc.)
- Django-Template-Tags und URLs
- Funktionale Elemente (Formulare, Buttons) — nur ihr Aussehen ändert sich
- Struktur von Tabellen-Daten
- Elemente werden nicht gelöscht oder verschoben ohne Rückfrage
