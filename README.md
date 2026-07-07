# SafeDrive 🚖🛡️

A **passenger-safety-first ride-hailing platform** built with **Django + Django Channels (WebSockets)**, vanilla HTML/CSS/JS, and Leaflet/OpenStreetMap maps (no API keys required).

> The original brief mentioned Prisma + Socket.io. Because the stack requested is **Django**, those are implemented with their Django equivalents:
> | Brief | This project |
> |---|---|
> | Prisma models | Django ORM models (`accounts/models.py`, `rides/models.py`) |
> | Socket.io | Django Channels consumers (`rides/consumers.py`) |
> | Express APIs | Django views (`*/views.py`) |

---

## ✨ Features

**Riders** — register/login, profile, trusted contacts, request ride (map pickup/destination), view nearby drivers, live tracking, trip sharing link, **SOS button**, ride history, rate drivers, report incidents.

**Drivers** — register/login, upload licence/ID/vehicle docs, verification status, accept/reject/start/end rides, live GPS streaming, history, ratings.

**Admin** — dashboard stats, driver approval/rejection/suspension, live ride monitoring map, trip logs, **real-time emergency center**, user management, ratings & reports.

**Safety systems**
1. **Live trip sharing** — secure `/rides/share/<token>/` URL, no account required, shows rider/driver/vehicle/location/destination/ETA/live map.
2. **SOS** — large always-visible red button during rides; stores an `EmergencyAlert`, captures GPS + trip, notifies trusted contacts and pushes to the admin dashboard live.
3. **Route deviation detection** — `rides/utils.py::evaluate_safety` flags significant route deviation, long stationary periods, and ETA overruns on every GPS ping.
4. **Real-time tracking** — Django Channels WebSockets stream driver location to rider, admin, and trip-share viewers.

---

## 🗂️ Project structure

```
kevo-project/
├── manage.py
├── requirements.txt
├── safedrive/            # project config (settings, urls, asgi, wsgi)
├── accounts/             # User, DriverProfile, TrustedContact, auth
├── rides/                # Ride, RideTracking, EmergencyAlert, Rating, IncidentReport
│   ├── consumers.py      # WebSocket consumers (tracking + admin alerts)
│   ├── services.py       # SOS + safety alert domain logic
│   ├── utils.py          # geo math + route-deviation detection
│   └── management/commands/seed_data.py
├── dashboard/            # admin dashboard views
├── templates/            # all HTML pages
└── static/               # css/style.css, js/tracking.js, js/sos.js
```

---

## 🚀 Quick start (local)

```bash
# 1. create + activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2. install dependencies
pip install -r requirements.txt

# 3. environment file
cp .env.example .env          # (Windows: copy .env.example .env)

# 4. database
python manage.py makemigrations accounts rides
python manage.py migrate

# 5. demo data (creates admin + riders + drivers + trips)
python manage.py seed_data

# 6. run (ASGI server with WebSocket support)
python manage.py runserver
```

Open http://127.0.0.1:8000

**Demo logins** (password: `password123`):
| Role | Email |
|---|---|
| Admin | `admin@safedrive.test` |
| Rider | `rider1@safedrive.test` |
| Approved driver | `driver1@safedrive.test` |
| Pending driver | `driver3@safedrive.test` |

> `runserver` automatically uses Daphne (ASGI) because `daphne` is first in `INSTALLED_APPS`, so WebSockets work out of the box with the in-memory channel layer.

---

## 🧱 Database schema

### `accounts.User` (custom, extends `AbstractUser`)
`id, username, name, email (unique, login field), phone, password, role {rider|driver|admin}, status {active|suspended|pending}, created_at`

### `accounts.DriverProfile`
`id, user (1-1), license_number, vehicle_type, vehicle_number, verification_status {pending|approved|rejected|suspended}, license_document, id_card, vehicle_document, current_lat, current_lng, is_online`

### `accounts.TrustedContact`
`id, rider (FK User), name, phone, email, created_at`

### `rides.Ride`
`id, rider (FK), driver (FK, nullable), pickup_location, pickup_lat/lng, destination, destination_lat/lng, planned_route (JSON), status {requested|accepted|ongoing|completed|cancelled|rejected}, start_time, end_time, eta_minutes, share_token (UUID), created_at`

### `rides.RideTracking`
`id, ride (FK), latitude, longitude, timestamp`  — append-only GPS breadcrumb.

### `rides.EmergencyAlert`
`id, ride (FK, nullable), rider (FK), raised_by (FK), kind {sos|route_deviation|stationary|eta_exceeded|incident}, location, latitude, longitude, message, status {active|acknowledged|resolved}, created_at, resolved_at`

### `rides.Rating`
`id, ride (1-1), rider (FK), driver (FK), score (1-5), review, created_at`

### `rides.IncidentReport`
`id, ride (FK, nullable), reporter (FK), category, description, resolved, created_at`

---

## 🔌 WebSocket endpoints

| URL | Purpose | Auth |
|---|---|---|
| `ws/ride/<ride_id>/` | Bi-directional ride tracking. Driver sends `{action:"location", lat, lng}`; everyone receives `location` / `alert` / `status` events. | Participant, admin, or `?token=<share_token>` |
| `ws/admin/alerts/` | Live feed of new emergency alerts. | Admin only |

---

## 🌐 Key HTTP routes

- `/` landing · `/accounts/register|login|profile|trusted-contacts|driver/verification`
- `/rides/rider` · `/rides/request` · `/rides/track/<id>` · `/rides/sos/<id>` (POST) · `/rides/history` · `/rides/rate/<id>` · `/rides/report`
- `/rides/share/<uuid>` public trip share (no login)
- `/rides/driver` · `/rides/driver/accept|reject|start|end/<id>` · `/rides/driver/ratings`
- `/dashboard/` admin home · `/dashboard/drivers` · `/dashboard/monitoring` · `/dashboard/emergency` · `/dashboard/users/...`

---

## 🛡️ Security notes

- CSRF protection on all POST forms and fetch calls (`X-CSRFToken`).
- Email-based authentication, hashed passwords, Django password validators.
- Authorisation checks per view and per WebSocket connection (participant / admin / share-token).
- `AllowedHostsOriginValidator` on WebSockets.
- Production hardening (HSTS, secure cookies, SSL redirect) auto-enabled when `DEBUG=False`.

---

## ☁️ Deployment

1. **Set environment** (`.env` or platform vars):
   ```
   DEBUG=False
   SECRET_KEY=<long-random>
   ALLOWED_HOSTS=yourdomain.com
   REDIS_URL=redis://<host>:6379/0
   ```
   Uncomment `channels-redis` in `requirements.txt` — Redis is required as the channel layer across multiple workers in production.

2. **Static & media**
   ```bash
   python manage.py collectstatic --noinput
   python manage.py migrate
   ```

3. **Run with an ASGI server** (Daphne or Uvicorn):
   ```bash
   daphne -b 0.0.0.0 -p 8000 safedrive.asgi:application
   ```
   Put **Nginx** in front for TLS + static/media serving, and proxy `/ws/` to the ASGI app with `Upgrade`/`Connection` headers.

4. **Database** — switch `DATABASES` to PostgreSQL for production (set `ENGINE=django.db.backends.postgresql`).

5. **Real notifications** — replace the body of `rides/notifications.py::_send_to_contact` with a Twilio (SMS) / SendGrid (email) integration.

### Example `Procfile` (Render/Railway/Heroku-style)
```
web: daphne -b 0.0.0.0 -p $PORT safedrive.asgi:application
release: python manage.py migrate
```

---

## 🧩 Extending

- **Real routing/ETA**: swap `rides/utils.py::build_straight_route` for an OSRM or Google Directions call.
- **Push notifications**: add a service worker + Web Push in `static/js`.
- **Payments**: add a `Payment` model + Stripe to the ride lifecycle.
