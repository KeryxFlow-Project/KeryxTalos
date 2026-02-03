"""Tests for the Task Scheduler."""

import asyncio
from datetime import UTC, datetime, time, timedelta

import pytest

from keryxflow.agent.scheduler import (
    ScheduledTask,
    TaskFrequency,
    TaskResult,
    TaskScheduler,
    TaskStatus,
    get_task_scheduler,
)


class TestTaskFrequency:
    """Tests for TaskFrequency enum."""

    def test_frequency_values(self):
        """Test task frequency values."""
        assert TaskFrequency.ONCE.value == "once"
        assert TaskFrequency.HOURLY.value == "hourly"
        assert TaskFrequency.DAILY.value == "daily"
        assert TaskFrequency.WEEKLY.value == "weekly"
        assert TaskFrequency.MONTHLY.value == "monthly"


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self):
        """Test task status values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestScheduledTask:
    """Tests for ScheduledTask dataclass."""

    def test_create_task(self):
        """Test creating a scheduled task."""
        async def callback():
            pass

        task = ScheduledTask(
            id="test_task",
            name="Test Task",
            frequency=TaskFrequency.DAILY,
            callback=callback,
        )

        assert task.id == "test_task"
        assert task.name == "Test Task"
        assert task.frequency == TaskFrequency.DAILY
        assert task.status == TaskStatus.PENDING
        assert task.run_count == 0
        assert task.enabled is True

    def test_to_dict(self):
        """Test converting to dictionary."""
        async def callback():
            pass

        task = ScheduledTask(
            id="test",
            name="Test",
            frequency=TaskFrequency.WEEKLY,
            callback=callback,
            run_count=5,
        )

        data = task.to_dict()

        assert data["id"] == "test"
        assert data["name"] == "Test"
        assert data["frequency"] == "weekly"
        assert data["run_count"] == 5


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_create_result(self):
        """Test creating a task result."""
        now = datetime.now(UTC)
        result = TaskResult(
            task_id="test",
            success=True,
            started_at=now,
            completed_at=now + timedelta(seconds=5),
            duration_ms=5000.0,
        )

        assert result.task_id == "test"
        assert result.success is True
        assert result.duration_ms == 5000.0
        assert result.error is None

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        now = datetime.now(UTC)
        result = TaskResult(
            task_id="test",
            success=False,
            started_at=now,
            completed_at=now,
            duration_ms=100.0,
            error="Test error",
        )

        data = result.to_dict()

        assert data["task_id"] == "test"
        assert data["success"] is False
        assert data["error"] == "Test error"


class TestTaskScheduler:
    """Tests for TaskScheduler class."""

    def test_create_scheduler(self):
        """Test creating a scheduler."""
        scheduler = TaskScheduler()

        assert scheduler._tasks == {}
        assert scheduler._running is False

    def test_add_task(self):
        """Test adding a task."""
        scheduler = TaskScheduler()
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1

        task = scheduler.add_task(
            id="test_task",
            name="Test Task",
            frequency=TaskFrequency.DAILY,
            callback=callback,
            run_at_time=time(12, 0),
        )

        assert task.id == "test_task"
        assert "test_task" in scheduler._tasks
        assert task.next_run is not None

    def test_add_duplicate_task_raises(self):
        """Test that adding duplicate task raises."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.ONCE,
            callback=callback,
        )

        with pytest.raises(ValueError, match="already exists"):
            scheduler.add_task(
                id="test",
                name="Test 2",
                frequency=TaskFrequency.ONCE,
                callback=callback,
            )

    def test_remove_task(self):
        """Test removing a task."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.ONCE,
            callback=callback,
        )

        result = scheduler.remove_task("test")

        assert result is True
        assert "test" not in scheduler._tasks

    def test_remove_nonexistent_task(self):
        """Test removing non-existent task."""
        scheduler = TaskScheduler()

        result = scheduler.remove_task("nonexistent")

        assert result is False

    def test_enable_disable_task(self):
        """Test enabling and disabling tasks."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.DAILY,
            callback=callback,
        )

        # Disable
        result = scheduler.disable_task("test")
        assert result is True
        assert scheduler._tasks["test"].enabled is False

        # Enable
        result = scheduler.enable_task("test")
        assert result is True
        assert scheduler._tasks["test"].enabled is True

    def test_get_task(self):
        """Test getting a task by ID."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.ONCE,
            callback=callback,
        )

        task = scheduler.get_task("test")
        assert task is not None
        assert task.id == "test"

        task = scheduler.get_task("nonexistent")
        assert task is None

    def test_list_tasks(self):
        """Test listing all tasks."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="task1",
            name="Task 1",
            frequency=TaskFrequency.DAILY,
            callback=callback,
        )
        scheduler.add_task(
            id="task2",
            name="Task 2",
            frequency=TaskFrequency.WEEKLY,
            callback=callback,
        )

        tasks = scheduler.list_tasks()

        assert len(tasks) == 2
        task_ids = [t["id"] for t in tasks]
        assert "task1" in task_ids
        assert "task2" in task_ids

    @pytest.mark.asyncio
    async def test_run_task_now(self):
        """Test running a task immediately."""
        scheduler = TaskScheduler()
        call_count = 0

        async def callback():
            nonlocal call_count
            call_count += 1

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.DAILY,
            callback=callback,
        )

        result = await scheduler.run_task_now("test")

        assert result is not None
        assert result.success is True
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_run_task_now_not_found(self):
        """Test running non-existent task."""
        scheduler = TaskScheduler()

        result = await scheduler.run_task_now("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_run_task_with_error(self):
        """Test running a task that raises an error."""
        scheduler = TaskScheduler()

        async def failing_callback():
            raise ValueError("Test error")

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.ONCE,
            callback=failing_callback,
        )

        result = await scheduler.run_task_now("test")

        assert result is not None
        assert result.success is False
        assert "Test error" in result.error

    @pytest.mark.asyncio
    async def test_start_stop_scheduler(self):
        """Test starting and stopping the scheduler."""
        scheduler = TaskScheduler(check_interval_seconds=1)

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.HOURLY,
            callback=callback,
        )

        await scheduler.start()
        assert scheduler._running is True

        # Let it run briefly
        await asyncio.sleep(0.1)

        await scheduler.stop()
        assert scheduler._running is False

    def test_calculate_next_run_once(self):
        """Test calculating next run for ONCE frequency."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        task = ScheduledTask(
            id="test",
            name="Test",
            frequency=TaskFrequency.ONCE,
            callback=callback,
            run_count=0,
        )

        next_run = scheduler._calculate_next_run(task)
        assert next_run is not None

        # After running once
        task.run_count = 1
        next_run = scheduler._calculate_next_run(task)
        assert next_run is None

    def test_calculate_next_run_hourly(self):
        """Test calculating next run for HOURLY frequency."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        task = ScheduledTask(
            id="test",
            name="Test",
            frequency=TaskFrequency.HOURLY,
            callback=callback,
        )

        next_run = scheduler._calculate_next_run(task)

        assert next_run is not None
        assert next_run > datetime.now(UTC)
        assert next_run.minute == 0

    def test_calculate_next_run_daily(self):
        """Test calculating next run for DAILY frequency."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        task = ScheduledTask(
            id="test",
            name="Test",
            frequency=TaskFrequency.DAILY,
            callback=callback,
            run_at_time=time(14, 30),
        )

        next_run = scheduler._calculate_next_run(task)

        assert next_run is not None
        assert next_run.hour == 14
        assert next_run.minute == 30

    def test_get_stats(self):
        """Test getting scheduler statistics."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.DAILY,
            callback=callback,
        )

        stats = scheduler.get_stats()

        assert stats["tasks_scheduled"] == 1
        assert stats["tasks_enabled"] == 1
        assert stats["running"] is False

    @pytest.mark.asyncio
    async def test_execution_history(self):
        """Test execution history tracking."""
        scheduler = TaskScheduler()

        async def callback():
            pass

        scheduler.add_task(
            id="test",
            name="Test",
            frequency=TaskFrequency.DAILY,
            callback=callback,
        )

        await scheduler.run_task_now("test")
        await scheduler.run_task_now("test")

        history = scheduler.get_execution_history()

        assert len(history) == 2
        assert all(h["task_id"] == "test" for h in history)


class TestGetTaskScheduler:
    """Tests for get_task_scheduler function."""

    def test_returns_singleton(self):
        """Test that function returns singleton."""
        scheduler1 = get_task_scheduler()
        scheduler2 = get_task_scheduler()

        assert scheduler1 is scheduler2

    def test_creates_scheduler(self):
        """Test that function creates scheduler."""
        scheduler = get_task_scheduler()

        assert isinstance(scheduler, TaskScheduler)
