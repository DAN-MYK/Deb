"""
Tests for async worker utility module.

Tests background task execution, callbacks, threading behavior,
and error handling for async operations.
"""
import threading
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

from app.gui.utils.async_worker import AsyncWorker, run_in_thread


class TestAsyncWorker:
    """Test AsyncWorker class for background tasks."""

    def test_init_with_required_params(self) -> None:
        """Test initialization with required parameters."""
        task = Mock()
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(
            task=task,
            on_complete=on_complete,
            on_error=on_error
        )

        assert worker.task == task
        assert worker.on_complete == on_complete
        assert worker.on_error == on_error
        assert worker.on_progress is None
        assert worker.thread is None
        assert not worker.is_running()

    def test_init_with_optional_progress_callback(self) -> None:
        """Test initialization with optional progress callback."""
        task = Mock()
        on_complete = Mock()
        on_error = Mock()
        on_progress = Mock()

        worker = AsyncWorker(
            task=task,
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress
        )

        assert worker.on_progress == on_progress

    def test_start_creates_thread(self) -> None:
        """Test that start() creates a daemon thread."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        assert worker.thread is not None
        assert isinstance(worker.thread, threading.Thread)
        assert worker.thread.daemon

        # Wait for thread to complete
        worker.thread.join(timeout=1)

        # Verify task was executed
        task.assert_called_once()

    def test_start_already_running_does_nothing(self) -> None:
        """Test that start() does nothing if already running."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker._is_running = True  # Simulate already running

        worker.start()

        assert worker.thread is None  # No new thread created

    def test_successful_task_execution(self) -> None:
        """Test successful task execution calls on_complete."""
        result = "success"
        task = Mock(return_value=result)
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        # Wait for task to complete
        worker.thread.join(timeout=1)

        task.assert_called_once()
        on_complete.assert_called_once_with(result)
        on_error.assert_not_called()
        assert not worker.is_running()

    def test_task_exception_calls_on_error(self) -> None:
        """Test that task exception calls on_error callback."""
        error = ValueError("Task failed")
        task = Mock(side_effect=error)
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        # Wait for task to complete
        worker.thread.join(timeout=1)

        task.assert_called_once()
        on_complete.assert_not_called()
        on_error.assert_called_once_with(error)
        assert not worker.is_running()

    def test_task_with_slow_execution(self) -> None:
        """Test task with slower execution time."""
        def slow_task() -> str:
            time.sleep(0.1)
            return "done"

        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(slow_task, on_complete, on_error)
        worker.start()

        # Check that it's running immediately
        time.sleep(0.01)
        assert worker.is_running()

        # Wait for completion
        worker.thread.join(timeout=1)

        on_complete.assert_called_once_with("done")
        on_error.assert_not_called()
        assert not worker.is_running()

    def test_task_with_no_return_value(self) -> None:
        """Test task that returns None."""
        task = Mock(return_value=None)
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        worker.thread.join(timeout=1)

        task.assert_called_once()
        on_complete.assert_called_once_with(None)
        on_error.assert_not_called()

    def test_multiple_workers_run_independently(self) -> None:
        """Test that multiple workers can run independently."""
        task1 = Mock(return_value="result1")
        task2 = Mock(return_value="result2")
        on_complete1 = Mock()
        on_complete2 = Mock()
        on_error = Mock()

        worker1 = AsyncWorker(task1, on_complete1, on_error)
        worker2 = AsyncWorker(task2, on_complete2, on_error)

        worker1.start()
        worker2.start()

        worker1.thread.join(timeout=1)
        worker2.thread.join(timeout=1)

        task1.assert_called_once()
        task2.assert_called_once()
        on_complete1.assert_called_once_with("result1")
        on_complete2.assert_called_once_with("result2")
        on_error.assert_not_called()

    def test_is_running_state_transitions(self) -> None:
        """Test is_running() returns correct state throughout lifecycle."""
        def task_with_delay() -> str:
            time.sleep(0.1)
            return "done"

        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task_with_delay, on_complete, on_error)

        # Before start
        assert not worker.is_running()

        # After start
        worker.start()
        time.sleep(0.01)
        assert worker.is_running()

        # After completion
        worker.thread.join(timeout=1)
        assert not worker.is_running()

    def test_task_raising_runtime_error(self) -> None:
        """Test handling of RuntimeError in task."""
        error = RuntimeError("Critical error")
        task = Mock(side_effect=error)
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        worker.thread.join(timeout=1)

        on_error.assert_called_once_with(error)
        on_complete.assert_not_called()

    def test_task_raising_custom_exception(self) -> None:
        """Test handling of custom exception in task."""
        class CustomError(Exception):
            pass

        error = CustomError("Custom error message")
        task = Mock(side_effect=error)
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        worker.thread.join(timeout=1)

        on_error.assert_called_once_with(error)

    @patch("app.gui.utils.async_worker.logger")
    def test_logging_on_success(self, mock_logger: Mock) -> None:
        """Test that successful execution logs correctly."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        worker.thread.join(timeout=1)

        # Verify logging calls
        assert mock_logger.info.call_count >= 2
        mock_logger.error.assert_not_called()

    @patch("app.gui.utils.async_worker.logger")
    def test_logging_on_error(self, mock_logger: Mock) -> None:
        """Test that errors are logged correctly."""
        error = ValueError("Test error")
        task = Mock(side_effect=error)
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker.start()

        worker.thread.join(timeout=1)

        # Verify error logging
        mock_logger.error.assert_called_once()
        assert "failed" in str(mock_logger.error.call_args).lower()

    @patch("app.gui.utils.async_worker.logger")
    def test_warning_on_double_start(self, mock_logger: Mock) -> None:
        """Test that starting an already running worker logs a warning."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()

        worker = AsyncWorker(task, on_complete, on_error)
        worker._is_running = True

        worker.start()

        mock_logger.warning.assert_called_once()
        assert "already running" in str(mock_logger.warning.call_args).lower()


class TestRunInThread:
    """Test run_in_thread convenience function."""

    def test_run_in_thread_creates_and_starts_worker(self) -> None:
        """Test that run_in_thread creates and starts worker."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()

        worker = run_in_thread(task, on_complete, on_error)

        assert isinstance(worker, AsyncWorker)
        assert worker.thread is not None
        assert worker.thread.is_alive() or task.call_count > 0  # Either running or already completed

        # Wait for completion
        worker.thread.join(timeout=1)

        task.assert_called_once()
        on_complete.assert_called_once_with("result")

    def test_run_in_thread_with_progress_callback(self) -> None:
        """Test run_in_thread with optional progress callback."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()
        on_progress = Mock()

        worker = run_in_thread(task, on_complete, on_error, on_progress)

        assert worker.on_progress == on_progress

        worker.thread.join(timeout=1)

    def test_run_in_thread_returns_started_worker(self) -> None:
        """Test that returned worker is already started."""
        task = Mock(return_value="result")
        on_complete = Mock()
        on_error = Mock()

        worker = run_in_thread(task, on_complete, on_error)

        # Worker should be running immediately after return
        time.sleep(0.01)
        assert worker.thread is not None
        assert worker.thread.is_alive() or not worker.is_running()  # Either running or finished

        worker.thread.join(timeout=1)

    def test_run_in_thread_handles_task_error(self) -> None:
        """Test that run_in_thread handles errors correctly."""
        error = RuntimeError("Task error")
        task = Mock(side_effect=error)
        on_complete = Mock()
        on_error = Mock()

        worker = run_in_thread(task, on_complete, on_error)

        worker.thread.join(timeout=1)

        on_error.assert_called_once_with(error)
        on_complete.assert_not_called()

    def test_run_in_thread_multiple_concurrent_tasks(self) -> None:
        """Test multiple concurrent tasks via run_in_thread."""
        task1 = Mock(return_value="result1")
        task2 = Mock(return_value="result2")
        on_complete1 = Mock()
        on_complete2 = Mock()
        on_error = Mock()

        worker1 = run_in_thread(task1, on_complete1, on_error)
        worker2 = run_in_thread(task2, on_complete2, on_error)

        worker1.thread.join(timeout=1)
        worker2.thread.join(timeout=1)

        on_complete1.assert_called_once_with("result1")
        on_complete2.assert_called_once_with("result2")
