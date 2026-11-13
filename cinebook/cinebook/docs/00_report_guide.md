# Assembling the PDF report (15–25 pages excl. code)

Required order: **title page → project overview → Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → conclusion → references**.

| Section | Source |
|---|---|
| Title page | Fill in the template: project title "CineBook – Movie Ticketing System", team table (USN/Name), and each member's contribution if in a team |
| Overview, Task 1 | `01_task1_object_basics.md` |
| Task 2 | Insert the PNGs from `docs/uml/png/` + the explanation column from `02_task2_uml.md` |
| Task 3 | `03_task3_analysis.md` |
| Task 4 | `04_task4_design.md` (include short snippets of `legacy/cinebook_v0.py` vs the new facade) |
| Task 5 | `05_task5_patterns.md` + the before/after PNGs (`*_before.png`, `*_after.png`) |
| Conclusion | What improved: removed god class and the cancel-all bug, new payment method / pricing rule / notifier / report = new class and no edit to booking code; 14 automated tests; state machine enforces valid transitions |
| References | Bahrami (OO Systems Development Using UML) chapters 1–10; Gamma et al., *Design Patterns* |

Include screenshots from `docs/screenshots/` (login, shows, seat selection with student pricing, booking confirmed, my bookings, admin), plus the output of `python -m unittest discover -s tests -v` (28 tests covering domain, patterns and the REST API).
For Task 5 also include `10_architecture_tiers.png` to show front end / back end / database.
Be ready in the viva/demo to explain every class and each pattern's "why", and to add a small change live (e.g. a new `FestivalPricing` strategy or a new payment method).
