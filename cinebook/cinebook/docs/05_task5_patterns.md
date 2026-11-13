# Task 5 – Design Patterns and Architecture (Unit V)

Diagrams (before/after for each): `docs/uml/09_patterns_before_after.puml`. Architecture: `08_package_layers.puml`.

| # | Pattern (category) | Where | Problem in the project | Why this over alternatives |
|---|---|---|---|---|
| 1 | **Singleton** (creational) | `data/database.py` | Repositories each opened their own SQLite connection → inconsistent transactions | Needs exactly one shared connection; a module-level global is untestable, Singleton gives `reset_instance()` for tests |
| 2 | **Factory Method** (creational) | `patterns/payments.py` | `if method == "upi" … elif …` in booking code | Each creator subclass decides its processor, so new methods = new class, no edit to booking code. Simple Factory/dict would still need edits to a central function; Abstract Factory is overkill (no families of products) |
| 3 | **Facade** (structural) | `services/booking_facade.py` | CLI would need 5+ repositories, pricing, payment, notification | Single simple interface for the UI; Mediator not needed – no peer-to-peer communication |
| 4 | **Strategy** (behavioral) | `patterns/pricing.py` | Pricing rules (seat type, weekend, student) duplicated and nested | Rules are interchangeable algorithms chosen at run time; Decorator would also work for stacking, but the business rule is "one rule wins", not "all stack" |
| 5 | **Observer** (behavioral) | `patterns/observers.py` | Email notification hard-coded inside booking | Decouples booking from any number of notifiers; adding SMS/audit needed no change to the facade |
| 6 | **Template Method** (behavioral) | `patterns/reports.py` | Each report repeats fetch → summarise → format | Fixed workflow with varying steps; subclasses override only the steps |

## Code snippets
**Singleton**
```python
@classmethod
def get_instance(cls, path="cinebook.db"):
    if cls._instance is None:
        cls._instance = cls(path)
    return cls._instance
```
**Factory Method**
```python
class PaymentCreator(ABC):
    @abstractmethod
    def create_processor(self) -> PaymentProcessor: ...
    def process(self, amount, details):
        return self.create_processor().charge(amount, details)
class UPICreator(PaymentCreator):
    def create_processor(self): return UPIProcessor()
```
**Facade** – `book_tickets()` coordinates repositories, `select_pricing`, `get_creator().process`, `publisher.notify`.
**Strategy**
```python
def select_pricing(show, customer):
    if customer.is_student: return StudentDiscountPricing()
    if show.start_time.weekday() >= 5: return WeekendPricing()
    return StandardPricing()
```
**Observer**
```python
def notify(self, event, booking):
    for o in list(self._observers):
        o.update(event, booking)
```
**Template Method**
```python
def generate(self):
    rows = self.fetch_rows()
    summary = self.summarise(rows)
    ...  # title, formatted rows, summary
```

## Patterns deliberately not used
Adapter, Decorator, Composite and Command were **not** added: the payment processors already share one interface (nothing to adapt), pricing rules do not stack (no decorator need), there is no tree structure (no composite), and there is no undo/queue requirement (no command). The assignment says not to force patterns.

## Architectural pattern: Layers
Presentation (`presentation/cli.py`, `main.py`) → Service (`services/booking_facade.py`) → Business rules/patterns (`patterns/`) → Domain (`domain/models.py`) and Data access (`data/`) → SQLite. Dependencies point downward only; the Domain imports nothing except `errors.py` (check with `grep -rn "^from\|^import" cinebook/domain`); the strategy/observer/report patterns are duck-typed against domain objects, so they import nothing from it.
