"""Pure process-tree classification logic: which processes belong under a
window-owning app root, and aggregate CPU/memory across a subtree.

Deliberately has no GTK import, so it's testable and importable without a
display — process_list.py is the GTK-facing caller.
"""

from __future__ import annotations

from typing import Protocol


class HasPidCpuMem(Protocol):
    pid: int
    cpu: float
    mem: float


def belongs_to_app(
    pid: int,
    ppid_of: dict[int, int],
    app_roots: set[int],
    cache: dict[int, bool] | None = None,
    depth: int = 0,
) -> bool:
    """Whether `pid` is a window-owning app root, or a descendant of one —
    walks the parent chain up via `ppid_of` until it hits a root, pid 0/self
    (no further parent), or a depth guard against malformed data."""
    cache = {} if cache is None else cache
    if pid in cache:
        return cache[pid]
    if depth > 50 or pid in app_roots:
        result = pid in app_roots
    else:
        parent = ppid_of.get(pid, 0)
        result = False if not parent or parent == pid else belongs_to_app(parent, ppid_of, app_roots, cache, depth + 1)
    cache[pid] = result
    return result


def subtree_totals(pid: int, children_of: dict[int, list[HasPidCpuMem]], cpu: float, mem: float) -> tuple[float, float]:
    """Sums cpu/mem for `pid` plus every descendant reachable via children_of."""
    for child in children_of.get(pid, []):
        c_cpu, c_mem = subtree_totals(child.pid, children_of, child.cpu, child.mem)
        cpu += c_cpu
        mem += c_mem
    return cpu, mem
