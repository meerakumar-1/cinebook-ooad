# CineBook – Movie Ticketing System (OOAD case study)

Full-stack movie ticketing application: **browser front end** (HTML/CSS/JavaScript) → **Flask REST back end** → **SQLite database**,
designed with object-oriented analysis & design and six GoF design patterns.
Python 3.10+, one dependency (Flask).

## Run the web application
```bash
pip install -r requirements.txt
python main.py web            # open http://localhost:5000   (add --reset to rebuild demo data, --port N to change port)
```
In **GitHub Codespaces**: run the two commands above; Codespaces forwards port 5000 and shows an "Open in Browser" popup (or open the **Ports** tab).

Demo accounts (password `demo1234`): `asha@example.com` (student → 15 % discount), `rohan@example.com`, `admin@orion.example` (admin). You can also register new customers.

Other modes (no Flask needed):
```bash
python main.py demo           # scripted console walkthrough (in-memory DB)
python main.py                # interactive console UI
python -m unittest discover -s tests -v    # 41 tests (domain, patterns, REST API)
```

## Features
- Customer: register/sign in, search & filter movies, live seat map with per-tier prices, instant price quote (student/weekend rules), **5-minute seat hold with countdown**, UPI/Card/Wallet payment (simulated, retry on failure), printable tickets, cancel with refund, booking history, notifications.
- Admin: dashboard (revenue, tickets, occupancy, revenue chart, booking status), recent bookings with cancel, text reports, add movies, schedule shows (screen-conflict check with a 15-minute turnaround).
- UI: dark/light theme, poster cards, mobile-friendly, keyboard-accessible seats, strict Content-Security-Policy (no inline scripts/styles).
- Rules enforced server-side: no double-booking, seat holds that expire, seat limits, role permissions, only the owner (or admin) can cancel, legal booking state transitions, login lockout after 5 failed attempts, sessions and notifications stored in the database.

## REST API (JSON, `Authorization: Bearer <token>` unless public)
| Method & path | Auth | Purpose |
|---|---|---|
| `POST /api/auth/register`, `/api/auth/login`, `/api/auth/logout`; `GET /api/me` | – / token | accounts and sessions |
| `GET /api/movies`, `/api/movies/<id>/shows`, `/api/shows/<id>/seats` | public | browsing |
| `POST /api/shows/<id>/quote` | customer | price preview for chosen seats |
| `POST /api/shows/<id>/hold` → `POST /api/bookings/<id>/pay` | customer | hold seats (PENDING, 5 min), then pay (retry allowed until expiry) |
| `POST /api/bookings/<id>/release`, `POST /api/bookings/<id>/cancel`, `GET /api/bookings`, `GET /api/bookings/<id>` | customer | free a hold / cancel & refund / history / one booking |
| `POST /api/bookings` | customer | one-shot hold + pay (convenience for API clients) |
| `GET /api/notifications` | customer | notification feed |
| `GET /api/admin/stats`, `GET /api/admin/bookings`, `GET /api/admin/reports/<revenue\|occupancy>` | admin | dashboard data, recent bookings, text reports |
| `GET /api/admin/screens`, `POST /api/admin/movies`, `POST /api/admin/shows` | admin | catalogue management |

Errors are JSON `{"error": "...", "type": "..."}` with 400 validation, 401 sign-in, 402 payment failed, 403 forbidden, 404 not found, 409 conflict (seat taken, bad state, screen busy), 410 hold expired, 429 too many login attempts.

## Project layout (Layers + MVC)
```
main.py                          entry point (web | demo | console)
cinebook/
  web/static/                    FRONT END: index.html, style.css, app.js, theme.js
  web/api.py, serializers.py     Controllers + JSON view (REST API)
  web/app.py                     Flask app factory, error mapping, observer wiring
  presentation/cli.py            alternative console UI
  services/booking_facade.py     Service layer     -> Facade
  services/auth_service.py       registration, login, bearer tokens (PBKDF2 password hashing in security.py)
  patterns/                      pricing (Strategy), payments (Factory Method), observers (Observer), reports (Template Method)
  domain/models.py               Domain layer (entities, state machine, inheritance, composition)
  data/database.py               DATA ACCESS -> Singleton (+ lock)   |  repositories.py, schema.sql, seed.py
legacy/cinebook_v0.py            "Before" baseline (god class) used for the before/after comparison
docs/                            Task 1-5 write-ups, UML (docs/uml/*.puml + png/), UI screenshots
tests/                           unittest suite (test_cinebook.py, test_api.py)
```

## Where each pattern is implemented
| Pattern | Category | Location |
|---|---|---|
| Singleton | Creational | `cinebook/data/database.py` – `DatabaseManager` |
| Factory Method | Creational | `cinebook/patterns/payments.py` – `PaymentCreator` and subclasses |
| Facade | Structural | `cinebook/services/booking_facade.py` – `BookingFacade` |
| Strategy | Behavioral | `cinebook/patterns/pricing.py` – `PricingStrategy` and subclasses |
| Observer | Behavioral | `cinebook/patterns/observers.py` – publisher + Email/SMS/Audit/InApp observers |
| Template Method | Behavioral | `cinebook/patterns/reports.py` – `ReportGenerator` |

Architectural pattern: **Layers**, with **MVC** inside the web presentation layer (see `docs/05_task5_patterns.md`).

## Assignment → files
| Task | Documentation | Code |
|---|---|---|
| 1 Object basics | `docs/01_task1_object_basics.md` | `domain/models.py` |
| 2 UML | `docs/02_task2_uml.md`, `docs/uml/` | – |
| 3 OO analysis | `docs/03_task3_analysis.md` | `domain/`, `services/` |
| 4 OO design | `docs/04_task4_design.md` | `legacy/cinebook_v0.py` vs `cinebook/` |
| 5 Patterns & architecture | `docs/05_task5_patterns.md` | `cinebook/patterns/`, `data/database.py`, `services/`, `web/` |

## Known limitations (be upfront about these in the report/viva)
- Demo-grade security: no HTTPS, no password reset, demo passwords are public, login lockout is in memory. Do not deploy as is.
- Payment gateways are simulated (validation only); card details are never stored.
- Seat holds expire lazily: a stale hold is swept on the next request that touches seats (no background timer), which is why seats free up exactly when anyone next looks.
- One server process: a lock makes seat check + insert atomic inside it; several processes on one SQLite file would need DB-level constraints.
- Show times are naive server-local times (no time zones).
- Database files from older versions are rejected with a clear message; delete `cinebook.db` or run `python main.py web --reset`.

## Push to GitHub
```bash
git init && git add . && git commit -m "CineBook: full-stack OOAD case study"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```
