"""Task scheduler for periodic agent tasks.

This module provides scheduling capabilities for:
- Daily close tasks (end of trading day)
- Weekly review tasks
- Periodic reflections
- Custom scheduled tasks
"""

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from enum import Enum
from typing import Any

from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class TaskFrequency(str, Enum):
    """Frequency of scheduled tasks."""

    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskStatus(str, Enum):
    """Status of a scheduled task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """Definition of a scheduled task."""

    id: str
    name: str
    frequency: TaskFrequency
    callback: Callable[[], Coroutine[Any, Any, Any]]

    # Schedule configuration
    run_at_time: time | None = None  # Time of day to run (for DAILY/WEEKLY)
    run_on_day: int | None = None  # Day of week (0=Mon) or month (1-31)

    # State
    status: TaskStatus = TaskStatus.PENDING
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None

    # Configuration
    enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 60

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "frequency": self.frequency.value,
            "status": self.status.value,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    success: bool
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "error": self.error,
            "data": self.data,
        }


@dataclass
class SchedulerStats:
    """Statistics for the scheduler."""

    tasks_executed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    total_execution_time_ms: float = 0
    last_execution_time: datetime | None = None


class TaskScheduler:
    """Scheduler for periodic agent tasks.

    The TaskScheduler manages scheduled tasks like:
    - Daily closing reflection
    - Weekly performance review
    - Periodic health checks

    Example:
        scheduler = TaskScheduler()

        # Add daily reflection task
        scheduler.add_task(
            id="daily_reflection",
            name="Daily Trading Reflection",
            frequency=TaskFrequency.DAILY,
            callback=reflection_engine.daily_reflection,
            run_at_time=time(23, 0),  # Run at 11 PM
        )

        # Start the scheduler
        await scheduler.start()
    """

    def __init__(self, check_interval_seconds: int = 60):
        """Initialize the scheduler.

        Args:
            check_interval_seconds: How often to check for due tasks.
        """
        self._tasks: dict[str, ScheduledTask] = {}
        self._check_interval = check_interval_seconds
        self._running = False
        self._event_bus = get_event_bus()
        self._stats = SchedulerStats()
        self._execution_history: list[TaskResult] = []
        self._scheduler_task: asyncio.Task | None = None

    def add_task(
        self,
        id: str,
        name: str,
        frequency: TaskFrequency,
        callback: Callable[[], Coroutine[Any, Any, Any]],
        run_at_time: time | None = None,
        run_on_day: int | None = None,
        enabled: bool = True,
    ) -> ScheduledTask:
        """Add a scheduled task.

        Args:
            id: Unique task identifier
            name: Human-readable task name
            frequency: How often to run
            callback: Async function to execute
            run_at_time: Time of day to run (for daily/weekly)
            run_on_day: Day of week (0=Mon) or month (1-31)
            enabled: Whether task is enabled

        Returns:
            The created ScheduledTask
        """
        if id in self._tasks:
            raise ValueError(f"Task '{id}' already exists")

        task = ScheduledTask(
            id=id,
            name=name,
            frequency=frequency,
            callback=callback,
            run_at_time=run_at_time,
            run_on_day=run_on_day,
            enabled=enabled,
        )

        # Calculate initial next_run
        task.next_run = self._calculate_next_run(task)

        self._tasks[id] = task

        logger.info(
            "task_scheduled",
            task_id=id,
            frequency=frequency.value,
            next_run=task.next_run.isoformat() if task.next_run else None,
        )

        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task.

        Args:
            task_id: ID of the task to remove

        Returns:
            True if removed, False if not found
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info("task_removed", task_id=task_id)
            return True
        return False

    def enable_task(self, task_id: str) -> bool:
        """Enable a task.

        Args:
            task_id: ID of the task

        Returns:
            True if enabled, False if not found
        """
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._tasks[task_id].next_run = self._calculate_next_run(self._tasks[task_id])
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Disable a task.

        Args:
            task_id: ID of the task

        Returns:
            True if disabled, False if not found
        """
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            return True
        return False

    def get_task(self, task_id: str) -> ScheduledTask | None:
        """Get a task by ID.

        Args:
            task_id: ID of the task

        Returns:
            ScheduledTask or None
        """
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks.

        Returns:
            List of task dictionaries
        """
        return [task.to_dict() for task in self._tasks.values()]

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_loop())

        logger.info("scheduler_started", task_count=len(self._tasks))

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task

        logger.info("scheduler_stopped")

    async def run_task_now(self, task_id: str) -> TaskResult | None:
        """Run a task immediately.

        Args:
            task_id: ID of the task to run

        Returns:
            TaskResult or None if task not found
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None

        return await self._execute_task(task)

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.now(UTC)

                # Check each task
                for task in self._tasks.values():
                    if not task.enabled:
                        continue

                    if task.next_run and now >= task.next_run:
                        await self._execute_task(task)

                # Wait before next check
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scheduler_loop_error", error=str(e))
                await asyncio.sleep(self._check_interval)

    async def _execute_task(self, task: ScheduledTask) -> TaskResult:
        """Execute a single task.

        Args:
            task: Task to execute

        Returns:
            TaskResult
        """
        started_at = datetime.now(UTC)
        task.status = TaskStatus.RUNNING

        # Publish event
        await self._event_bus.publish(
            Event(
                type=EventType.SYSTEM_STARTED,
                data={
                    "event_type": "scheduler.task_started",
                    "task_id": task.id,
                    "task_name": task.name,
                },
            )
        )

        try:
            # Execute the callback
            await task.callback()

            # Success
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            task.status = TaskStatus.COMPLETED
            task.last_run = completed_at
            task.run_count += 1
            task.next_run = self._calculate_next_run(task)

            self._stats.tasks_executed += 1
            self._stats.tasks_succeeded += 1
            self._stats.total_execution_time_ms += duration_ms
            self._stats.last_execution_time = completed_at

            result = TaskResult(
                task_id=task.id,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )

            logger.info(
                "task_completed",
                task_id=task.id,
                duration_ms=duration_ms,
            )

        except Exception as e:
            # Failure
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            task.status = TaskStatus.FAILED
            task.last_run = completed_at
            task.error_count += 1
            task.last_error = str(e)
            task.next_run = self._calculate_next_run(task)

            self._stats.tasks_executed += 1
            self._stats.tasks_failed += 1

            result = TaskResult(
                task_id=task.id,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                error=str(e),
            )

            logger.error(
                "task_failed",
                task_id=task.id,
                error=str(e),
            )

        # Store in history
        self._execution_history.append(result)
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]

        # Publish completion event
        await self._event_bus.publish(
            Event(
                type=EventType.SYSTEM_STARTED,
                data={
                    "event_type": "scheduler.task_completed",
                    "task_id": task.id,
                    "success": result.success,
                    "duration_ms": duration_ms,
                },
            )
        )

        return result

    def _calculate_next_run(self, task: ScheduledTask) -> datetime | None:
        """Calculate the next run time for a task.

        Args:
            task: The task

        Returns:
            Next run datetime or None for ONCE tasks that have run
        """
        now = datetime.now(UTC)

        if task.frequency == TaskFrequency.ONCE:
            if task.run_count > 0:
                return None
            return task.next_run or now

        if task.frequency == TaskFrequency.HOURLY:
            # Next hour
            next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_run

        if task.frequency == TaskFrequency.DAILY:
            # Next occurrence of run_at_time
            run_time = task.run_at_time or time(0, 0)
            next_run = now.replace(
                hour=run_time.hour,
                minute=run_time.minute,
                second=0,
                microsecond=0,
            )
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        if task.frequency == TaskFrequency.WEEKLY:
            # Next occurrence of run_on_day at run_at_time
            run_day = task.run_on_day if task.run_on_day is not None else 0  # Monday
            run_time = task.run_at_time or time(0, 0)

            # Find next occurrence of the day
            days_ahead = run_day - now.weekday()
            if days_ahead < 0:  # Target day already happened this week
                days_ahead += 7

            next_run = now.replace(
                hour=run_time.hour,
                minute=run_time.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=days_ahead)

            if next_run <= now:
                next_run += timedelta(days=7)

            return next_run

        if task.frequency == TaskFrequency.MONTHLY:
            # Next occurrence of run_on_day
            run_day = task.run_on_day if task.run_on_day is not None else 1
            run_time = task.run_at_time or time(0, 0)

            # Try this month
            try:
                next_run = now.replace(
                    day=run_day,
                    hour=run_time.hour,
                    minute=run_time.minute,
                    second=0,
                    microsecond=0,
                )
            except ValueError:
                # Day doesn't exist in this month, use last day
                import calendar

                last_day = calendar.monthrange(now.year, now.month)[1]
                next_run = now.replace(
                    day=last_day,
                    hour=run_time.hour,
                    minute=run_time.minute,
                    second=0,
                    microsecond=0,
                )

            if next_run <= now:
                # Move to next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)

            return next_run

        return now + timedelta(hours=1)  # Default fallback

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "tasks_scheduled": len(self._tasks),
            "tasks_enabled": sum(1 for t in self._tasks.values() if t.enabled),
            "tasks_executed": self._stats.tasks_executed,
            "tasks_succeeded": self._stats.tasks_succeeded,
            "tasks_failed": self._stats.tasks_failed,
            "success_rate": (
                self._stats.tasks_succeeded / self._stats.tasks_executed
                if self._stats.tasks_executed > 0
                else 0
            ),
            "total_execution_time_ms": self._stats.total_execution_time_ms,
            "avg_execution_time_ms": (
                self._stats.total_execution_time_ms / self._stats.tasks_executed
                if self._stats.tasks_executed > 0
                else 0
            ),
            "last_execution_time": (
                self._stats.last_execution_time.isoformat()
                if self._stats.last_execution_time
                else None
            ),
            "running": self._running,
        }

    def get_execution_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent task execution history.

        Args:
            limit: Maximum results to return

        Returns:
            List of TaskResult dictionaries
        """
        return [r.to_dict() for r in self._execution_history[-limit:]]


# Global instance
_scheduler: TaskScheduler | None = None


def get_task_scheduler() -> TaskScheduler:
    """Get the global task scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


async def setup_default_tasks(scheduler: TaskScheduler | None = None) -> None:
    """Set up default scheduled tasks.

    Args:
        scheduler: Scheduler to use. Uses global if None.
    """
    if scheduler is None:
        scheduler = get_task_scheduler()

    from keryxflow.agent.reflection import get_reflection_engine

    reflection = get_reflection_engine()

    # Daily reflection at 23:00 UTC
    scheduler.add_task(
        id="daily_reflection",
        name="Daily Trading Reflection",
        frequency=TaskFrequency.DAILY,
        callback=reflection.daily_reflection,
        run_at_time=time(23, 0),
    )

    # Weekly reflection on Sunday at 23:30 UTC
    scheduler.add_task(
        id="weekly_reflection",
        name="Weekly Trading Reflection",
        frequency=TaskFrequency.WEEKLY,
        callback=reflection.weekly_reflection,
        run_at_time=time(23, 30),
        run_on_day=6,  # Sunday
    )

    logger.info("default_tasks_configured", task_count=len(scheduler._tasks))
