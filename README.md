# EventRadar

**EventRadar** is a web-based event recommendation and tracking platform. Its aim is to bring concerts, theatre performances, cinema screenings, and sports matches together in a single place, and to help users discover, follow, and get notified about events that match their interests and location — instead of manually checking multiple ticket platforms (Biletix, Passo, Ticketmaster, etc.) to avoid missing out on things they'd actually want to attend.

## Why EventRadar

Existing event platforms require users to check several sites, don't proactively notify them when something relevant appears, and don't personalize results based on past interest or precise location. EventRadar addresses this by combining:

- A single catalogue for all event categories
- Location-aware event discovery
- A "follow event" mechanism with personalized email notifications
- An admin panel for keeping the event database accurate
- Automatic import of events from external ticket-provider sources

## Features

- **Account management** — register, log in/out, update profile and password
- **Event browsing** — filter by category (theatre, cinema, sports, concerts) and by location
- **Event details** — name, date, time, venue, description, and category-specific info (e.g. director/cast for cinema, performer for theatre, teams for sports, artist for concerts)
- **Follow / unfollow events** — track events you care about
- **Email notifications** — opt-in alerts about followed events, sent via SMTP when configured, or logged to the database otherwise
- **Admin panel** — create, update, and delete events and manage users
- **Ticket-site import** — pull events in bulk from external ticket-provider sources into the local catalogue
- **Google Maps integration** — venue search and directions via Maps web links (no API key required)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python (standard library HTTP server, no external framework) |
| Database | SQLite (`eventradar.sqlite3`) |
| Frontend | Single-page `index.html` (HTML/CSS/JavaScript) |
| Notifications | SMTP (optional, via environment variables) |
| Maps | Google Maps web links |

## Project Structure

```
EventRadar-Project/
├── server.py            # Backend HTTP server and REST API
├── event_importer.py    # Imports events from external ticket-provider sources
├── eventradar.sqlite3   # SQLite database file
├── index.html           # Frontend single-page application
├── LICENSE
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.13 (or a compatible Python 3 version)

### Run the backend

```bash
cd EventRadar-Project
python server.py
```

The API will be available at:

```
http://127.0.0.1:8000
```

Open `index.html` in a browser to use the frontend (it talks to the local server above).

### Default admin account

```
email:    admin@eventradar.com
password: admin123
```

> Change these credentials before any real deployment.

## Database

`server.py` creates and manages the following SQLite tables:

| Table | Purpose |
|---|---|
| `users` | Registered users |
| `sessions` | Login/auth token records |
| `events` | Event catalogue |
| `follows` | Which users follow which events |
| `event_sources` | Maps imported events back to their ticket-site source/ID |
| `import_runs` | Summary of each import operation |
| `notification_logs` | Record of sent/queued notification emails |

## API Reference

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/health` | Public | Health check |
| POST | `/api/auth/register` | Public | Create an account |
| POST | `/api/auth/login` | Public | Log in, returns a token |
| POST | `/api/auth/logout` | Authenticated | Invalidate the current session |
| GET | `/api/me` | Authenticated | Get current user's profile |
| PUT | `/api/me` | Authenticated | Update current user's profile |
| POST | `/api/me/notifications` | Authenticated | Toggle email notifications |
| GET | `/api/events` | Public | List/browse events |
| GET | `/api/events/{id}` | Public | Get event details |
| POST | `/api/events` | Admin | Create an event |
| PUT | `/api/events/{id}` | Admin | Update an event |
| DELETE | `/api/events/{id}` | Admin | Remove an event |
| POST | `/api/events/{id}/follow` | Authenticated | Follow an event |
| DELETE | `/api/events/{id}/follow` | Authenticated | Unfollow an event |
| GET | `/api/me/followed` | Authenticated | List events the user follows |
| GET | `/api/users` | Admin | List users |
| POST | `/api/users` | Admin | Create a user |
| PUT | `/api/users/{email}` | Admin | Update a user |
| DELETE | `/api/users/{email}` | Admin | Delete a user |
| GET | `/api/import-events` | Admin | Preview an import from ticket sites |
| POST | `/api/import-events` | Admin | Run an import and save results to the database |

Example: importing events with an authenticated admin token (PowerShell):

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" `
    -Body '{"email":"admin@eventradar.com","password":"admin123"}'

$headers = @{ Authorization = "Bearer $($login.token)" }

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/import-events?limit=30" `
    -Headers $headers -ContentType "application/json" -Body "{}"
```

The same action is available from the admin panel via the **Import Ticket Sites** button.

## Email Notifications

Users can opt in to email notifications for followed events via `POST /api/me/notifications`. To send real emails, set the following environment variables before starting the server:

```bash
export EVENTRADAR_SMTP_HOST="smtp.example.com"
export EVENTRADAR_SMTP_PORT="587"
export EVENTRADAR_SMTP_USER="user@example.com"
export EVENTRADAR_SMTP_PASSWORD="password"
export EVENTRADAR_SMTP_FROM="EventRadar <user@example.com>"

python server.py
```

If SMTP is not configured, notifications are recorded in the `notification_logs` table with status `logged` instead of being sent.

## Architecture

The backend is organized as a layered client-server system:

- **UI Layer** — the `index.html` frontend renders event listings, event details, follow/unfollow controls, and the admin panel, and collects user input.
- **Controller / Service Layer** — `server.py` routes incoming requests, enforces authentication and admin authorization, and implements the core business logic (registration, login/session handling, event CRUD, follow/unfollow, recommendation and notification logic).
- **Data Access Layer** — persistence operations are handled through repository-style functions in `server.py` that read from and write to SQLite, keeping database access isolated from business logic.
- **External Services Layer** — dedicated integration points handle SMTP delivery (`event notifications`), Google Maps links (venue lookup/directions), and ticket-provider imports (`event_importer.py`).

This separation means a ticket-provider source, the mail service, or the persistence mechanism can be swapped without changing the request-handling or business-logic code.

## Design Priorities

A few qualities were treated as first-class goals while building EventRadar, not just the functional features:

- **Responsiveness** — event browsing, search, and filtering should feel instant to the user.
- **Timely notifications** — followed-event alerts are only useful if they arrive while the user can still act on them, so notification delivery is treated as time-sensitive.
- **Resilience to third-party outages** — if a ticket-provider source is temporarily unavailable, the system falls back to the last known data rather than showing an error.
- **Data protection** — passwords are never stored in plain text, sessions expire after inactivity, and location data is only used to power nearby-event filtering.
- **Accurate, deduplicated data** — imports are tracked per source (`event_sources`, `import_runs`) so the same event isn't added to the catalogue twice.

## Roadmap

Ideas identified for future iterations:

- Smarter recommendations based on a user's full interaction history, not just follows
- Push notifications / mobile app support
- Finer-grained location filtering (radius-based, not just city/district)
- Rate-limiting and account lockout on repeated failed logins

## License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for details.
