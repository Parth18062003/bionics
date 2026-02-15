"""
Phase 2 Tests — Priority-Based Scheduler
===========================================
Validates:
- Higher priority dequeued first
- Remove task from queue
- Empty queue returns None
- Priority update works via lazy deletion
"""

from __future__ import annotations

import uuid

import pytest

from aadap.orchestrator.scheduler import TaskScheduler


class TestSchedulerPriority:
    """Verify priority ordering."""

    def test_higher_priority_first(self):
        """Tasks with higher priority are dequeued before lower."""
        scheduler = TaskScheduler()
        low = uuid.uuid4()
        mid = uuid.uuid4()
        high = uuid.uuid4()

        scheduler.schedule(low, priority=1)
        scheduler.schedule(mid, priority=5)
        scheduler.schedule(high, priority=10)

        assert scheduler.next() == high
        assert scheduler.next() == mid
        assert scheduler.next() == low

    def test_fifo_on_equal_priority(self):
        """Tasks with equal priority are dequeued in insertion order."""
        scheduler = TaskScheduler()
        first = uuid.uuid4()
        second = uuid.uuid4()
        third = uuid.uuid4()

        scheduler.schedule(first, priority=5)
        scheduler.schedule(second, priority=5)
        scheduler.schedule(third, priority=5)

        assert scheduler.next() == first
        assert scheduler.next() == second
        assert scheduler.next() == third


class TestSchedulerOperations:
    """Verify queue operations."""

    def test_empty_queue_returns_none(self):
        """An empty scheduler returns None on next()."""
        scheduler = TaskScheduler()
        assert scheduler.next() is None

    def test_peek_does_not_remove(self):
        """peek() returns the top item without removing it."""
        scheduler = TaskScheduler()
        task_id = uuid.uuid4()
        scheduler.schedule(task_id, priority=1)

        assert scheduler.peek() == task_id
        assert scheduler.pending_count() == 1

    def test_remove_task(self):
        """remove() takes a task out of the queue."""
        scheduler = TaskScheduler()
        task_a = uuid.uuid4()
        task_b = uuid.uuid4()

        scheduler.schedule(task_a, priority=10)
        scheduler.schedule(task_b, priority=5)

        removed = scheduler.remove(task_a)
        assert removed is True

        # Next should be task_b
        assert scheduler.next() == task_b

    def test_remove_nonexistent_returns_false(self):
        """Removing a task that isn't queued returns False."""
        scheduler = TaskScheduler()
        assert scheduler.remove(uuid.uuid4()) is False

    def test_pending_count(self):
        """pending_count() tracks the number of active entries."""
        scheduler = TaskScheduler()
        assert scheduler.pending_count() == 0

        ids = [uuid.uuid4() for _ in range(3)]
        for i, tid in enumerate(ids):
            scheduler.schedule(tid, priority=i)

        assert scheduler.pending_count() == 3

        scheduler.next()
        assert scheduler.pending_count() == 2

    def test_contains(self):
        """contains() checks if a task is in the queue."""
        scheduler = TaskScheduler()
        task_id = uuid.uuid4()

        assert scheduler.contains(task_id) is False
        scheduler.schedule(task_id, priority=1)
        assert scheduler.contains(task_id) is True

    def test_clear(self):
        """clear() empties the entire queue."""
        scheduler = TaskScheduler()
        for _ in range(5):
            scheduler.schedule(uuid.uuid4(), priority=1)

        scheduler.clear()
        assert scheduler.pending_count() == 0
        assert scheduler.next() is None


class TestSchedulerPriorityUpdate:
    """Verify re-scheduling with updated priority."""

    def test_update_priority(self):
        """Re-scheduling a task updates its priority."""
        scheduler = TaskScheduler()
        task_low = uuid.uuid4()
        task_high = uuid.uuid4()

        scheduler.schedule(task_low, priority=1)
        scheduler.schedule(task_high, priority=10)

        # Boost task_low above task_high
        scheduler.schedule(task_low, priority=20)

        # task_low should now be first
        assert scheduler.next() == task_low
        assert scheduler.next() == task_high

    def test_pending_count_after_update(self):
        """Re-scheduling doesn't increase the logical count."""
        scheduler = TaskScheduler()
        task_id = uuid.uuid4()

        scheduler.schedule(task_id, priority=1)
        assert scheduler.pending_count() == 1

        scheduler.schedule(task_id, priority=10)
        assert scheduler.pending_count() == 1
