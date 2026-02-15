"""
AADAP — Priority-Based Task Scheduler
========================================
In-memory priority queue for scheduling task execution.

Architecture layer: L5 (Orchestration).

Usage:
    scheduler = TaskScheduler()
    scheduler.schedule(task_id, priority=10)
    next_id = scheduler.next()
"""

from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(order=True, slots=True)
class _PriorityEntry:
    """
    Heap entry.  Higher numeric priority = execute first,
    so we negate the priority for min-heap ordering.
    """

    neg_priority: int
    insertion_order: int = field(compare=True)
    task_id: uuid.UUID = field(compare=False)
    removed: bool = field(default=False, compare=False)


class TaskScheduler:
    """
    Priority-based task scheduler using an in-memory min-heap.

    Higher ``priority`` values are dequeued first (most urgent).
    Ties are broken by insertion order (FIFO).

    Thread safety: NOT thread-safe.  Designed for use within
    the async orchestration loop (single-threaded event loop).
    """

    def __init__(self) -> None:
        self._heap: list[_PriorityEntry] = []
        self._entries: dict[uuid.UUID, _PriorityEntry] = {}
        self._counter: int = 0

    def schedule(self, task_id: uuid.UUID, priority: int = 0) -> None:
        """
        Enqueue or update a task's priority.

        If the task is already queued, it is logically removed and
        re-inserted with the new priority (lazy deletion pattern).
        """
        if task_id in self._entries:
            # Mark old entry as removed (lazy deletion)
            self._entries[task_id].removed = True

        entry = _PriorityEntry(
            neg_priority=-priority,
            insertion_order=self._counter,
            task_id=task_id,
        )
        self._counter += 1
        self._entries[task_id] = entry
        heapq.heappush(self._heap, entry)

    def next(self) -> uuid.UUID | None:
        """
        Dequeue and return the highest-priority task ID.

        Returns ``None`` if the queue is empty.
        Skips lazily-removed entries.
        """
        while self._heap:
            entry = heapq.heappop(self._heap)
            if not entry.removed:
                del self._entries[entry.task_id]
                return entry.task_id
        return None

    def peek(self) -> uuid.UUID | None:
        """
        Return the highest-priority task ID without removing it.

        Returns ``None`` if the queue is empty.
        """
        while self._heap:
            entry = self._heap[0]
            if not entry.removed:
                return entry.task_id
            heapq.heappop(self._heap)
        return None

    def remove(self, task_id: uuid.UUID) -> bool:
        """
        Remove a task from the queue.

        Returns ``True`` if the task was in the queue.
        """
        entry = self._entries.pop(task_id, None)
        if entry is None:
            return False
        entry.removed = True
        return True

    def pending_count(self) -> int:
        """Return the number of tasks currently in the queue."""
        return len(self._entries)

    def contains(self, task_id: uuid.UUID) -> bool:
        """Check if a task is currently queued."""
        return task_id in self._entries

    def clear(self) -> None:
        """Remove all tasks from the queue."""
        self._heap.clear()
        self._entries.clear()
        self._counter = 0
