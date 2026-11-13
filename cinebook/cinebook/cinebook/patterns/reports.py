"""PATTERN (Behavioral): Template Method - fixed report workflow, subclasses supply the varying steps."""
from abc import ABC, abstractmethod


class ReportGenerator(ABC):
    def __init__(self, queries): self._q = queries

    def generate(self) -> str:  # the template method
        rows = self.fetch_rows()
        summary = self.summarise(rows)
        lines = [self.title(), "-" * len(self.title()), *[self.format_row(r) for r in rows], "-" * len(self.title()), summary]
        return "\n".join(lines)

    @abstractmethod
    def title(self) -> str: ...
    @abstractmethod
    def fetch_rows(self) -> list: ...
    @abstractmethod
    def format_row(self, row) -> str: ...
    @abstractmethod
    def summarise(self, rows) -> str: ...


class RevenueReport(ReportGenerator):
    def title(self): return "REVENUE BY MOVIE"
    def fetch_rows(self): return self._q.revenue_by_movie()
    def format_row(self, r): return f"{r[0]:<28} tickets={r[1]:<3} revenue=Rs.{r[2]:.2f}"
    def summarise(self, rows): return f"Total revenue: Rs.{sum(r[2] for r in rows):.2f}"


class OccupancyReport(ReportGenerator):
    def title(self): return "OCCUPANCY BY SHOW"
    def fetch_rows(self): return self._q.occupancy_by_show()
    def format_row(self, r): return f"{r[0]:<28} {r[1][:16]}  {r[3]}/{r[2]} ({100 * r[3] / r[2]:.0f}%)"
    def summarise(self, rows):
        sold, cap = sum(r[3] for r in rows), sum(r[2] for r in rows)
        return f"Overall occupancy: {100 * sold / cap:.1f}%" if cap else "No shows"


REPORTS = {"revenue": RevenueReport, "occupancy": OccupancyReport}
