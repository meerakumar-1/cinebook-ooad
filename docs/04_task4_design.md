# Task 4 – Object-Oriented Design (Unit IV)

**"Before" = `legacy/cinebook_v0.py`**, a single-class baseline kept in the repo so the before/after comparison is concrete.

## 4.1 Corollaries
| Corollary | Found in the original | Changed |
|---|---|---|
| Uncoupled design, less information content | `CinemaSystem` exposed raw lists/dicts; callers reached into `show["price"]` | Private state, typed entities, repositories hide SQL; CLI talks only to `BookingFacade` |
| Single purpose | `CinemaSystem` did booking, pricing, payment, notification, reporting | One reason to change per class (Strategy, Factory, Observer, Template, Repository) |
| Large number of simpler classes | 1 class | 40+ small classes (including the exception hierarchy) |
| Strong mapping | Dicts did not match the real-world concepts | Domain classes mirror Movie, Show, Seat, Booking, Ticket, Payment |
| Standardization | Ad-hoc return values (`None` + `print`) | Common abstract interfaces + one exception hierarchy (`errors.py`) |
| Designing with inheritance | None / hard-coded `if` | Only where behaviour varies: User, Strategy, Processor, Report, Observer. Booking states use a transition table instead of subclasses because states have no distinct behaviour. |

## 4.2 Coupling and cohesion
| Class | Coupling | Cohesion |
|---|---|---|
| `CinemaSystem` (before) | Very high: pricing, payment, notification, reporting all inside | Low (coincidental) |
| `web/api.py` controllers | Low: each function only translates HTTP ↔ facade calls | High: one endpoint, one job |
| `BookingFacade` | Medium by design: depends on abstractions (strategy, creator, publisher) and repositories | High (functional): all methods are use-case orchestration |
| `Booking` | Low: depends only on Customer/Show/Ticket | High: everything concerns booking state and totals |
| `*Repository` | Low: depend on the DB singleton + domain | High: persistence of one aggregate each |

**Before → after (CinemaSystem.book):** one 30-line method doing price loops, `if method == ...` chains, bookkeeping and `print("EMAIL...")` → `BookingFacade.book_tickets` delegating to `select_pricing()`, `get_creator().process()`, and `publisher.notify()`.

## 4.3 Visibility (UML: + public, − private, # protected)
| Class | Public protocol (external) | Private/protected (internal) |
|---|---|---|
| Booking | +status (read-only), +total_amount, +confirm(), +cancel(), +expire() | −_status, −_ALLOWED, −_move() |
| User | +id, +name, +email (read-only), +role() | −_email |
| DatabaseManager | +get_instance(), +connection, +transaction() | −_conn, −_instance |
| ReportGenerator | +generate() | #title(), #fetch_rows(), #format_row(), #summarise() (hooks for subclasses) |
| AuthService | +register(), +login(), +user_for_token(), +logout() | −_tokens, −_issue_token() |
| BookingEventPublisher | +subscribe(), +unsubscribe(), +notify() | −_observers |
| BookingFacade | +list_movies(), +seat_map(), +book_tickets(), +cancel_booking(), +generate_report() | −_db, −_clock, repositories |

The public protocol is what callers may rely on; the private/protected protocol can change without breaking them.

## 4.4 Attributes and operations (UML notation)
- `-status: BookingStatus = PENDING`
- `+created_at: datetime = now()`
- `+is_student: bool = false`, `+phone: str = ""`
- `+base_price: float`, `+duration_min: int {> 0}`
- `+book_tickets(customer_id: int, show_id: int, seat_labels: List<str>, method: str, details: dict): Booking`
- `+cancel_booking(booking_id: int): Booking`
- `+generate_report(admin_id: int, kind: str): str`
- `+price(show: Show, seat: Seat): float`
- `+charge(amount: float, details: dict): PaymentResult`
- `+update(event: BookingEvent, booking: Booking): void`
- `+seat_by_label(label: str): Seat`

## 4.5 Design pitfalls found and fixed
| Pitfall | Where (before) | Fix |
|---|---|---|
| God class | `CinemaSystem` | Split into facade, repositories, strategies, creators, observers, reports |
| Public data members | `self.bookings`, `self.seats_taken` mutable from anywhere | Private state; `Booking._status` changed only via methods |
| Duplicated logic | Price multipliers repeated in `book()` | `SeatType.multiplier` + `PricingStrategy` |
| Type-code `if/elif` | Payment method chain | Factory Method + polymorphic processors |
| Missing invariant / bug | `cancel()` cancelled **every** booking and ignored the id; no state check | `cancel_booking(id)` loads one booking; `Booking._move()` rejects illegal transitions (tested in `test_state_machine`, `test_cancel_refunds_and_frees_seat`) |
| Hard-wired side effects | `print("EMAIL sent")` inside booking | Observer |
