# Task 3 – Object-Oriented Analysis (Unit III)

## 3.1 Actors
**Customer** (primary), **Admin** (primary), **Payment Gateway** (secondary/system; simulated by `PaymentProcessor`s).

## 3.2 Detailed use cases
### UC-Book Tickets
- **Actor:** Customer  **Pre-condition:** customer exists; show is in the future.
- **Main flow:** 1. Customer picks a show. 2. System displays seat map. 3. Customer selects 1–10 seats. 4. System checks every seat is free. 5. System prices each seat (pricing rule). 6. System creates a PENDING booking. 7. Customer pays (UPI/Card/Wallet). 8. System confirms the booking. 9. System notifies the customer.
- **Alternate flows:** 4a. Seat taken → error `SeatUnavailableError`, nothing saved. 7a. Payment fails → booking CANCELLED, seats released, failed payment kept for audit, `PaymentFailedError`. 3a. Unknown seat label / 0 or >10 seats → `ValidationError`.
- **Post-condition:** booking CONFIRMED, tickets issued, payment SUCCESS, notifications sent.

### UC-Cancel Booking
- **Actor:** Customer  **Pre-condition:** booking exists and is PENDING/CONFIRMED; show not started.
- **Main flow:** 1. Customer gives booking id. 2. System checks show has not started. 3. System cancels booking. 4. If paid, payment marked REFUNDED. 5. Seats become free. 6. Customer notified.
- **Alternate flows:** 2a. Show started → `ShowStartedError`. 3a. Already cancelled/expired → `InvalidStateTransition`.
- **Post-condition:** booking CANCELLED, seats available again.

### UC-Generate Report
- **Actor:** Admin  **Pre-condition:** user has role ADMIN.
- **Main flow:** 1. Admin selects report type. 2. System fetches aggregate data. 3. System formats rows and summary. 4. System displays report.
- **Alternate flows:** 1a. Non-admin → `PermissionDenied`. 1b. Unknown type → `ValidationError`.
- **Post-condition:** report text returned; no data changed.

## 3.3 Noun-phrase approach (from the three use cases above)
| Noun phrase | Classification | Reason |
|---|---|---|
| customer | Relevant → `Customer` | Actor with state and behaviour |
| admin | Relevant → `Admin` | Actor with a different role |
| show | Relevant → `Show` | Has time, price, movie, screen |
| movie | Relevant → `Movie` | Independent entity with attributes |
| screen | Relevant → `Screen` | Contains seats, has capacity |
| theatre | Relevant → `Theatre` | Owns screens |
| seat | Relevant → `Seat` | Has row, number, type |
| seat map | Irrelevant | A *view* computed from seats + bookings, not stored |
| booking | Relevant → `Booking` | Core entity with life cycle |
| ticket | Relevant → `Ticket` | One per seat, has price and code |
| payment | Relevant → `Payment` | Has method, amount, status |
| payment method (UPI/card/wallet) | Relevant → `PaymentProcessor` hierarchy | Differing behaviour |
| price / amount / total | Irrelevant as classes | Attributes (`Ticket.price`, `Booking.total_amount`) |
| pricing rule / discount | Relevant → `PricingStrategy` | Varying behaviour |
| notification, email, SMS | Relevant → `BookingObserver` subclasses | Reaction to events |
| report | Relevant → `ReportGenerator` | Has a fixed workflow |
| seat label | Irrelevant | Derived attribute of Seat |
| status | Irrelevant as class | Enum attribute of Booking |
| system | Irrelevant | The application itself |
| error | Irrelevant | Modelled as exceptions |
| refund | Fuzzy | Kept as a Payment *status* (REFUNDED); a `Refund` class would be needed only if partial refunds/fees existed |
| session / login | Fuzzy | Out of scope: the CLI takes a user id; a real app would add `Session` |
| hold / timeout | Fuzzy | Needed for EXPIRED; not yet implemented |

## 3.4 Use-case-driven confirmation
From `04_sequence_book.puml`: Facade, Repositories, PricingStrategy, PaymentCreator/Processor, Booking, Ticket, Payment, Publisher/Observers emerge. From `05_sequence_cancel.puml`: `Booking.cancel()` state rule, payment refund, notification. Facade and repositories are **design** classes added in Unit IV, not found in the nouns.

## 3.5 Relationships
- **Associations:** Customer–Booking (1..*), Show–Booking, Ticket–Seat, Screen–Show, Booking–Payment (0..1).
- **Super/sub:** User ← Customer, Admin; PricingStrategy, PaymentProcessor, ReportGenerator, BookingObserver hierarchies.
- **A-part-of:** Theatre◆Screen, Screen◆Seat, Booking◆Ticket (composition); Movie◇Show (aggregation).

## 3.6 Final attributes and methods
See `02_class.puml` and Task 4 (visibility and full operation signatures).
