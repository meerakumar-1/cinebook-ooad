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
python -m unittest discover -s tests -v    # 28 tests (domain, patterns, REST API)
```

## Features
- Customer: register/sign in, browse movies & upcoming shows, live seat map, price quote, UPI/Card/Wallet payment (simulated), multi-seat booking, cancel with refund, booking history, in-app notifications.
- Admin: revenue and occupancy reports, add movies, schedule shows (screen-conflict check with a 15-minute turnaround).
- Rules enforced server-side: no double-booking, seat limits, role permissions, only the owner (or admin) can cancel, legal booking state transitions.

## REST API (JSON, `Authorization: Bearer <token>` unless public)
| Method & path | Auth | Purpose |
|---|---|---|
| `POST /api/auth/register`, `/api/auth/login`, `/api/auth/logout`; `GET /api/me` | – / token | accounts and sessions |
| `GET /api/movies`, `/api/movies/<id>/shows`, `/api/shows/<id>/seats` | public | browsing |
| `POST /api/shows/<id>/quote` | customer | price preview for chosen seats |
| `POST /api/bookings`, `GET /api/bookings`, `POST /api/bookings/<id>/cancel` | customer | book / history / cancel |
| `GET /api/notifications` | customer | notification feed |
| `GET /api/admin/reports/<revenue\|occupancy>`, `GET /api/admin/screens`, `POST /api/admin/movies`, `POST /api/admin/shows` | admin | reports and catalogue |

Errors are JSON `{"error": "...", "type": "..."}` with 400 validation, 401 sign-in, 402 payment failed, 403 forbidden, 404 not found, 409 conflict (seat taken, bad state, screen busy).

## Project layout (Layers + MVC)
```
main.py                          entry point (web | demo | console)
cinebook/
  web/static/                    FRONT END: index.html, style.css, app.js
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
- Demo-grade security: no HTTPS, sessions are in memory (lost on restart), no rate limiting, demo passwords are public. Do not deploy as is.
- Payment gateways are simulated (validation only); card details are never stored.
- Single process: a lock makes seat check + insert atomic inside one server process, but several server processes on one SQLite file would need DB-level constraints.
- `EXPIRED` booking state is modelled but no timer triggers seat-hold expiry. Notification feed is in memory.
- Show times are naive server-local times (no time zones).
- If you ran an older version, delete `cinebook.db` (or use `--reset`) because the users table gained a `password_hash` column.

## Push to GitHub
```bash
git init && git add . && git commit -m "CineBook: full-stack OOAD case study"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```
