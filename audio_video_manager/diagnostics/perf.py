"""Instrumentation légère des durées / volumes (AVM-06G-P)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class PerfSpan:
    name: str
    seconds: float
    bytes_in: int = 0
    bytes_out: int = 0
    items: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerfSession:
    """Collecte des spans pour un job / un banc."""

    label: str = ""
    spans: list[PerfSpan] = field(default_factory=list)

    @contextmanager
    def span(
        self,
        name: str,
        *,
        bytes_in: int = 0,
        bytes_out: int = 0,
        items: int = 0,
        **extra: Any,
    ) -> Iterator[dict[str, Any]]:
        meta: dict[str, Any] = dict(extra)
        t0 = time.perf_counter()
        try:
            yield meta
        finally:
            dt = time.perf_counter() - t0
            self.spans.append(
                PerfSpan(
                    name=name,
                    seconds=dt,
                    bytes_in=int(meta.get("bytes_in", bytes_in) or 0),
                    bytes_out=int(meta.get("bytes_out", bytes_out) or 0),
                    items=int(meta.get("items", items) or 0),
                    extra={k: v for k, v in meta.items() if k not in ("bytes_in", "bytes_out", "items")},
                )
            )

    def record(
        self,
        name: str,
        seconds: float,
        *,
        bytes_in: int = 0,
        bytes_out: int = 0,
        items: int = 0,
        **extra: Any,
    ) -> None:
        self.spans.append(
            PerfSpan(
                name=name,
                seconds=seconds,
                bytes_in=bytes_in,
                bytes_out=bytes_out,
                items=items,
                extra=dict(extra),
            )
        )

    def total_seconds(self) -> float:
        return sum(s.seconds for s in self.spans)

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "total_seconds": round(self.total_seconds(), 4),
            "spans": [
                {
                    "name": s.name,
                    "seconds": round(s.seconds, 4),
                    "bytes_in": s.bytes_in,
                    "bytes_out": s.bytes_out,
                    "items": s.items,
                    **({"extra": s.extra} if s.extra else {}),
                }
                for s in self.spans
            ],
        }
