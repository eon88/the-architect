# The Architect

Life-design journaling application focused on the 7 Pillars of Life: Social, Financial, Spiritual, Craft/Career, Emotional/Intimacy, Intellectual, and Legacy.

## Stack

- **Backend:** FastAPI + SQLAlchemy (SQLite)
- **Frontend:** Vanilla HTML/CSS/JS — Matrix aesthetic (lime green `#00ff41` on black, monospace)
- **AI Pipeline:** Claude API for journal analysis and pillar momentum tracking

## Frontend Architecture

The `web_app/static/` directory contains three files:

| File | Purpose |
|------|---------|
| `index.html` | App shell, login screen, all section panels, ARIA markup |
| `style.css` | Design system: Matrix theme, responsive layout, animations, loading states, toasts |
| `script.js` | API calls, error handling, navigation state, character counters, loading management |

## Running Locally

```bash
cd web_app
pip install -r ../requirements.txt
uvicorn main:app --reload
```

Visit `http://localhost:8000`

## UX Features

- **Fully responsive** — 320px to 1920px (hamburger menu on mobile)
- **Button hierarchy** — Primary (Morning/Midday/Evening) vs Secondary (Reviews/Insights)
- **Animated loading states** — Pulsing dots + progress sweep + 5s timeout warning
- **Toast notifications** — Categorized errors (network, server, auth, validation, rate-limit) with Retry
- **Character counter** — Color-coded progress bar (gray → green → amber → red)
- **Navigation breadcrumbs** — `RITUAL > MORNING PROTOCOL > [LOADED]`
- **Daily progress strip** — Visual morning → midday → evening flow indicator
- **WCAG AA accessibility** — ARIA labels, focus states (green glow), keyboard shortcuts (`M`, `E`, `P`)
- **Keyboard navigation** — Tab through all interactive elements; `Escape` closes mobile menu

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `M` | Morning ritual |
| `E` | Evening reflection |
| `P` | Pillar map |
| `Escape` | Close mobile menu |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Login / create user by email |
| `GET` | `/ritual/morning/{user_id}` | Get morning brief |
| `POST` | `/ritual/evening` | Submit evening journal entry |
| `GET` | `/user/pillars/{user_id}` | Get all pillar states |
