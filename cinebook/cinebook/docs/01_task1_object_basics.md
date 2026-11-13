# Task 1 – Object Basics and Project Overview (Unit I)

## 1.1 Project overview
**CineBook** is a movie-ticketing system for a multiplex. **Users:** customers (browse, book, cancel) and admins (reports). **Problem solved:** replaces manual counter booking with seat-accurate online booking that prevents double-booking, prices tickets by seat type/day/customer, takes payment, and notifies the customer. **Main features:** browse movies & shows, live seat map, multi-seat booking, UPI/Card/Wallet payment, cancellation with refund, booking history, revenue/occupancy reports.
Stack: Python 3, SQLite (data-access layer), console UI.

## 1.2 Objects grouped into classes
| Class | State (attributes) | Behaviour (methods) |
|---|---|---|
| Movie | title, duration_min, genre, language, rating | validation on creation |
| Theatre | name, city, screens | – |
| Screen | name, seats | capacity(), seat_by_label() |
| Seat | row, number, seat_type | label() |
| Show | movie, screen, start_time, base_price | end_time() |
| User / Customer / Admin | name, email, phone, is_student | role() |
| Booking | customer, show, tickets, status, created_at | total_amount(), confirm(), cancel(), expire() |
| Ticket | seat, price, code | – |
| Payment | booking_id, method, amount, status, txn_ref | – |
| PricingStrategy (+3 subclasses) | – | price(show, seat) |
| PaymentCreator / PaymentProcessor | – | create_processor(), charge() |
| BookingEventPublisher / observers | observers list | subscribe(), notify(), update() |
| ReportGenerator (+2) | queries | generate() |
| BookingFacade | repositories, publisher, clock | book_tickets(), cancel_booking(), seat_map(), generate_report() |

## 1.3 CRC cards (6 classes)
| **Booking** | |
|---|---|
| Responsibilities | Hold customer, show and tickets; compute total; enforce legal status transitions |
| Collaborators | Customer, Show, Ticket |

| **BookingFacade** | |
|---|---|
| Responsibilities | Orchestrate booking/cancellation/report use cases; validate seats; wrap writes in a transaction |
| Collaborators | Repositories, PricingStrategy, PaymentCreator, BookingEventPublisher, Booking |

| **Show** | |
|---|---|
| Responsibilities | Know which movie plays on which screen, when, at what base price |
| Collaborators | Movie, Screen |

| **PricingStrategy** | |
|---|---|
| Responsibilities | Compute the price of one seat for one show under one rule |
| Collaborators | Show, Seat |

| **PaymentCreator** | |
|---|---|
| Responsibilities | Choose the right PaymentProcessor and charge it |
| Collaborators | PaymentProcessor, PaymentResult |

| **BookingEventPublisher** | |
|---|---|
| Responsibilities | Keep a list of observers and notify them on booking events |
| Collaborators | BookingObserver (Email/SMS/Audit), Booking |

### Collaboration for the use case "Book Tickets"
1. CLI → **BookingFacade**.`book_tickets()`
2. Facade → **Repositories** to load Customer/Show and the taken seats
3. Facade → **PricingStrategy**.`price()` for each Seat → creates **Tickets**
4. Facade → **Booking** (PENDING) → saved
5. Facade → **PaymentCreator**.`process()` → **PaymentProcessor**.`charge()`
6. Facade → **Booking**.`confirm()` (or `cancel()` on failure)
7. Facade → **BookingEventPublisher**.`notify()` → **EmailNotifier / SMSNotifier / AuditLogger**

## 1.4 OO concepts in the project
| Concept | Example (file) |
|---|---|
| Encapsulation & information hiding | `Booking._status` is private; only `confirm/cancel/expire` can change it and they enforce the transition table (`domain/models.py`). `DatabaseManager._conn` is hidden behind `connection` / `transaction()`. `User._email` is validated and read-only. |
| Class hierarchy | `User → Customer, Admin`; `PricingStrategy → Standard/Weekend/StudentDiscount`; `PaymentProcessor → UPI/Card/Wallet`; `ReportGenerator → Revenue/Occupancy` |
| Polymorphism | `strategy.price()`, `processor.charge()`, `observer.update()`, `user.role()` are called through the base type and resolved at run time |
| Aggregation / containment | Aggregation: `Movie` ◇— `Show` (movie outlives its shows). Composition: `Booking` ◆— `Ticket`, `Screen` ◆— `Seat`, `Theatre` ◆— `Screen` |
