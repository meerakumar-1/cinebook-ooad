# Task 2 – UML Modelling (Unit II)

PlantUML sources are in `docs/uml/*.puml`; pre-rendered PNGs in `docs/uml/png/`. Regenerate with
`java -jar plantuml.jar -tpng -o png docs/uml/*.puml` (or paste into plantuml.com / the VS Code PlantUML extension).

| Required diagram | File | What to say about it in the report |
|---|---|---|
| Use-case (≥5 use cases, include/extend) | `01_usecase.puml` | 14 use cases, 3 actors. Book Tickets **includes** View Seat Map, Make Payment, Apply Pricing Rule, Send Notification. Schedule Show **includes** Check Screen Conflicts. Refund Payment **extends** Cancel Booking (only when the booking had been paid). |
| Class (≥6 classes, multiplicity, roles, aggregation/composition, generalization) | `02_class.puml` | Generalization: User←Customer/Admin. Composition: Theatre◆Screen◆Seat, Booking◆Ticket. Aggregation: Movie◇Show. No association class/qualifier/N-ary was added because no relationship needed one – the assignment says to use them only where meaningful. |
| Object (snapshot) | `03_object.puml` | Asha's confirmed booking of C1, C2 with student pricing (2 × 318.75 = 637.50), matching the demo output. |
| Sequence ×2 | `04_sequence_book.puml`, `05_sequence_cancel.puml` | Book (browser → REST controller → auth → facade → repositories/strategy/factory/observer, with success/failure branch) and Cancel (ownership + state check + refund + notification). |
| State chart | `06_state_booking.puml` | Booking life cycle PENDING → CONFIRMED/CANCELLED/EXPIRED; implemented in `Booking._ALLOWED`. |
| Activity | `07_activity_booking.puml` | End-to-end booking workflow with decision points for seat availability and payment. |

Note: `EXPIRED` is modelled and enforced by the state machine (`Booking.expire()`) but no timer triggers it yet – say this in the report rather than claiming a hold-timeout feature.

**Extra (architecture, used in Task 5):** `08_package_layers.puml` (package diagram with dependency direction) and `10_architecture_tiers.puml` (browser ↔ Flask ↔ SQLite).
