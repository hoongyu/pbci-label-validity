"""Memory guard for the preprocessing sweeps.

On 2026-08-03 the machine bluescreened with DIRTY_NOWRITE_PAGES_CONGESTION
(0xFD) while four descriptive-variant workers were running. That bug check is
raised by the memory manager when dirty pages cannot be flushed fast enough
under sustained pressure — i.e. the system was thrashing.

The cause was ours in the sense that we chose the worker count, but the
underlying condition is that this machine has very little free memory to begin
with: measured after the reboot with **no** Python running, 2.07 GB free of
15.63 GB, with a single unrelated MCP server holding 5.6 GB. Four workers at
~1.3 GB each needed roughly 5.2 GB that did not exist.

Fewer workers alone is not a fix, because free memory depends on whatever else
the user is running and changes over the hours a sweep takes. This module makes
the pipeline refuse to proceed into conditions that caused the crash: every
subject-session checks free memory first and waits, rather than allocating into
a system that is already short.

`psutil` is already in `env/requirements.lock` (pulled in transitively), so this
adds no dependency.
"""

from __future__ import annotations

import time

import psutil

#: Refuse to begin a subject-session with less than this much RAM free.
#: One worker peaks near 1.3 GB, so this leaves headroom for it plus the
#: system rather than sizing exactly to the peak.
DEFAULT_MIN_FREE_GB = 3.0

#: How long to wait for memory to become available before giving up. A sweep
#: that stalls for this long needs a human, not more patience.
DEFAULT_TIMEOUT_S = 1800.0

POLL_S = 20.0


class InsufficientMemory(RuntimeError):
    """Raised when free memory stays below the floor for too long."""


def free_gb() -> float:
    return psutil.virtual_memory().available / 1024 ** 3


def total_gb() -> float:
    return psutil.virtual_memory().total / 1024 ** 3


def top_consumers(n: int = 5) -> list[tuple[str, float]]:
    """Largest resident processes, aggregated by name — for the error message."""
    totals: dict[str, float] = {}
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            info = proc.info
            if info["memory_info"] is None:
                continue
            totals[info["name"] or "?"] = (totals.get(info["name"] or "?", 0.0)
                                           + info["memory_info"].rss / 1024 ** 3)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(totals.items(), key=lambda kv: -kv[1])[:n]


def require_free_memory(minimum_gb: float = DEFAULT_MIN_FREE_GB, *,
                        timeout_s: float = DEFAULT_TIMEOUT_S,
                        label: str = "", verbose: bool = True) -> None:
    """Block until `minimum_gb` is free, or raise.

    Waiting rather than failing immediately is deliberate: memory freed by
    another worker finishing, or by the user closing something, lets the sweep
    continue on its own. Proceeding anyway is what crashed the machine.
    """
    deadline = time.time() + timeout_s
    warned = False
    while True:
        available = free_gb()
        if available >= minimum_gb:
            if warned and verbose:
                print(f"    memory recovered ({available:.2f} GB free), continuing",
                      flush=True)
            return
        if time.time() >= deadline:
            consumers = ", ".join(f"{name} {gb:.1f} GB" for name, gb in top_consumers())
            raise InsufficientMemory(
                f"only {available:.2f} GB free, need {minimum_gb:.2f} GB"
                f"{f' for {label}' if label else ''}, and it did not free up "
                f"within {timeout_s / 60:.0f} min. Largest consumers: {consumers}. "
                "Close something, or run fewer workers."
            )
        if not warned and verbose:
            print(f"    waiting for memory: {available:.2f} GB free, "
                  f"need {minimum_gb:.2f} GB{f' for {label}' if label else ''}",
                  flush=True)
            warned = True
        time.sleep(POLL_S)


def describe() -> str:
    return (f"{free_gb():.2f} GB free of {total_gb():.1f} GB; "
            + ", ".join(f"{name} {gb:.1f} GB" for name, gb in top_consumers(3)))
