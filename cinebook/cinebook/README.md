# CineBook – Movie Ticketing System (OOAD case study)

Object-oriented movie ticketing system with a SQLite data-access layer, built for the OOAD case study
"Applying Object-Oriented Analysis, Design and Design Patterns to design a Project".
Python 3.10+, **no third-party dependencies**.

## Run
```bash
python main.py demo      # scripted walkthrough (in-memory DB): booking, double-booking, bad payment, cancel, reports
python main.py           # interactive console (persists to cinebook.db; login ids: 1,2 = customers, 3 = admin)
python -m unittest discover -s tests -v   # 14 tests
```

## Project layout (Layered architecture)
```
main.py                         entry point
cinebook/
  presentation/cli.py           Presentation layer (talks only to the facade)
  services/booking_facade.py    Service layer      -> Facade
  patterns/                     Business rules
      pricing.py                                   -> Strategy
      payments.py                                  -> Factory Method
      observers.py                                 -> Observer
      reports.py                                   -> Template Method
  domain/models.py              Domain layer (entities, state machine, inheritance, composition)
  data/database.py              Data access        -> Singleton
  data/repositories.py, schema.sql, seed.py
legacy/cinebook_v0.py           "Before" baseline (god class) used for the before/after comparison
docs/                           Task 1-5 write-ups + UML (docs/uml/*.puml and rendered png/)
tests/                          unittest suite
```

## Where each pattern is implemented
| Pattern | Category | Location |
|---|---|---|
| Singleton | Creational | `cinebook/data/database.py` – `DatabaseManager` |
| Factory Method | Creational | `cinebook/patterns/payments.py` – `PaymentCreator` and subclasses |
| Facade | Structural | `cinebook/services/booking_facade.py` – `BookingFacade` |
| Strategy | Behavioral | `cinebook/patterns/pricing.py` – `PricingStrategy` and subclasses |
| Observer | Behavioral | `cinebook/patterns/observers.py` – `BookingEventPublisher` + notifiers |
| Template Method | Behavioral | `cinebook/patterns/reports.py` – `ReportGenerator` |

Architectural pattern: **Layers** (see `docs/uml/08_package_layers.puml`).

## Assignment → files
| Task | Documentation | Code |
|---|---|---|
| 1 Object basics | `docs/01_task1_object_basics.md` | `domain/models.py` |
| 2 UML | `docs/02_task2_uml.md`, `docs/uml/` | – |
| 3 OO analysis | `docs/03_task3_analysis.md` | `domain/`, `services/` |
| 4 OO design | `docs/04_task4_design.md` | `legacy/cinebook_v0.py` vs `cinebook/` |
| 5 Patterns & architecture | `docs/05_task5_patterns.md` | `cinebook/patterns/`, `data/database.py`, `services/` |

## Known limitations
- Console UI only; payment gateways are simulated (validation rules, no real network calls).
- `EXPIRED` booking state is modelled but no timer triggers seat-hold expiry yet.
- Single-process SQLite: the seat-availability check and insert are not safe under concurrent writers.

## Push to GitHub
```bash
cd cinebook
git init && git add . && git commit -m "CineBook: OOAD case study"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```
