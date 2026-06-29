from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class TraceBuilder:
    events: list[dict] = field(default_factory=list)

    def add(self, name: str, **fields: object) -> None:
        self.events.append({"name": name, "ts": perf_counter(), **fields})
