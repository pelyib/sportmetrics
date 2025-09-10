#!/usr/bin/env python3
"""
SportMetrics Queue Manager

Manages per-stat queues for session processing tasks using JSON storage with file locking.
Each stat type has its own queue file for isolation and parallel processing.
"""

import json
import time
import uuid
import fcntl
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# Configure logging
logger = logging.getLogger("SportMetrics.QueueManager")


@dataclass
class Task:
    """Represents a single processing task in a queue."""

    task_id: str
    session_file: str
    session_hash: str
    status: str  # pending, processing, completed, failed
    priority: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None


@dataclass
class QueueStats:
    """Statistics for a queue."""

    total_tasks: int
    pending: int
    processing: int
    completed: int
    failed: int


@dataclass
class QueueData:
    """Complete queue data structure."""

    stat_id: str
    stat_name: str
    version: str
    created: str
    last_updated: str
    stats: QueueStats
    tasks: List[Task]
    dead_letter_queue: List[Task]


class QueueManager:
    """Manages per-stat queues with JSON storage and file locking."""

    def __init__(self, queues_dir: str = "backend/src/automation/queues"):
        """
        Initialize the queue manager.

        Args:
            queues_dir: Directory containing queue files
        """
        self.queues_dir = Path(queues_dir).resolve()
        self.queues_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.queues_dir / "queue_index.json"

        logger.info(f"QueueManager initialized with directory: {self.queues_dir}")

        # Initialize index file if it doesn't exist
        self._ensure_index_exists()

    def _ensure_index_exists(self):
        """Ensure the queue index file exists."""
        if not self.index_file.exists():
            index_data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat() + "Z",
                "queues": [],
                "global_stats": {
                    "total_pending": 0,
                    "total_processing": 0,
                    "total_completed": 0,
                    "total_failed": 0,
                },
            }
            self._write_json_file(self.index_file, index_data)
            logger.info("Created queue index file")

    @contextmanager
    def _file_lock(self, file_path: Path, mode: str = "r"):
        """
        Context manager for file locking.

        Args:
            file_path: Path to the file to lock
            mode: File open mode
        """
        try:
            with open(file_path, mode, encoding="utf-8") as f:
                # Apply exclusive lock for writing, shared lock for reading
                lock_type = (
                    fcntl.LOCK_EX if "w" in mode or "a" in mode else fcntl.LOCK_SH
                )
                fcntl.flock(f.fileno(), lock_type)
                yield f
        except Exception as e:
            logger.error(f"File lock error for {file_path}: {e}")
            raise

    def _read_json_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read JSON file with locking.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON data
        """
        try:
            with self._file_lock(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return {}

    def _write_json_file(self, file_path: Path, data: Dict[str, Any]):
        """
        Write JSON file with locking and atomic operation.

        Args:
            file_path: Path to JSON file
            data: Data to write
        """
        # Write to temporary file first, then rename for atomicity
        temp_file = file_path.with_suffix(".tmp")

        try:
            with self._file_lock(temp_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()  # Ensure data is written to disk

            # Atomic rename
            temp_file.replace(file_path)

        except Exception as e:
            # Clean up temp file if something went wrong
            if temp_file.exists():
                temp_file.unlink()
            logger.error(f"Error writing JSON file {file_path}: {e}")
            raise

    def _get_queue_file_path(self, stat_id: str) -> Path:
        """Get the file path for a stat queue."""
        return self.queues_dir / f"{stat_id}_queue.json"

    def _ensure_queue_exists(self, stat_id: str, stat_name: str = None) -> bool:
        """
        Ensure a queue file exists for the given stat ID.

        Args:
            stat_id: Unique identifier for the stat
            stat_name: Human-readable name for the stat

        Returns:
            True if queue was created, False if it already existed
        """
        queue_file = self._get_queue_file_path(stat_id)

        if queue_file.exists():
            return False

        # Create new queue
        queue_data = QueueData(
            stat_id=stat_id,
            stat_name=stat_name or stat_id.replace("_", " ").title(),
            version="1.0",
            created=datetime.now().isoformat() + "Z",
            last_updated=datetime.now().isoformat() + "Z",
            stats=QueueStats(
                total_tasks=0, pending=0, processing=0, completed=0, failed=0
            ),
            tasks=[],
            dead_letter_queue=[],
        )

        # Write queue file
        self._write_json_file(queue_file, asdict(queue_data))

        # Update index
        self._add_queue_to_index(stat_id, queue_file.name)

        logger.info(f"Created new queue for stat: {stat_id}")
        return True

    def _add_queue_to_index(self, stat_id: str, queue_filename: str):
        """Add a queue to the index file."""
        index_data = self._read_json_file(self.index_file)

        # Check if queue already exists in index
        for queue_info in index_data.get("queues", []):
            if queue_info["stat_id"] == stat_id:
                return  # Already exists

        # Add new queue to index
        index_data.setdefault("queues", []).append(
            {
                "stat_id": stat_id,
                "queue_file": queue_filename,
                "status": "active",
                "last_processed": None,
            }
        )

        index_data["last_updated"] = datetime.now().isoformat() + "Z"

        self._write_json_file(self.index_file, index_data)

    def _load_queue_data(self, stat_id: str) -> Optional[QueueData]:
        """
        Load queue data for a stat.

        Args:
            stat_id: Stat identifier

        Returns:
            QueueData object or None if not found
        """
        queue_file = self._get_queue_file_path(stat_id)

        if not queue_file.exists():
            return None

        try:
            data = self._read_json_file(queue_file)
            if not data:
                return None

            # Convert dict to QueueData object
            stats_data = data.get("stats", {})
            stats = QueueStats(**stats_data)

            tasks_data = data.get("tasks", [])
            tasks = [Task(**task) for task in tasks_data]

            dlq_data = data.get("dead_letter_queue", [])
            dead_letter_queue = [Task(**task) for task in dlq_data]

            return QueueData(
                stat_id=data["stat_id"],
                stat_name=data["stat_name"],
                version=data["version"],
                created=data["created"],
                last_updated=data["last_updated"],
                stats=stats,
                tasks=tasks,
                dead_letter_queue=dead_letter_queue,
            )

        except Exception as e:
            logger.error(f"Error loading queue data for {stat_id}: {e}")
            return None

    def _save_queue_data(self, queue_data: QueueData):
        """
        Save queue data to file.

        Args:
            queue_data: QueueData to save
        """
        queue_data.last_updated = datetime.now().isoformat() + "Z"

        # Recalculate stats
        queue_data.stats.total_tasks = len(queue_data.tasks)
        queue_data.stats.pending = sum(
            1 for task in queue_data.tasks if task.status == "pending"
        )
        queue_data.stats.processing = sum(
            1 for task in queue_data.tasks if task.status == "processing"
        )
        queue_data.stats.completed = sum(
            1 for task in queue_data.tasks if task.status == "completed"
        )
        queue_data.stats.failed = sum(
            1 for task in queue_data.tasks if task.status == "failed"
        )

        queue_file = self._get_queue_file_path(queue_data.stat_id)
        self._write_json_file(queue_file, asdict(queue_data))

    def add_task_to_stat(
        self,
        stat_id: str,
        session_file: str,
        session_hash: str = None,
        priority: int = 1,
        stat_name: str = None,
    ) -> str:
        """
        Add a new task to a stat queue.

        Args:
            stat_id: Stat identifier
            session_file: Path to session file to process
            session_hash: Hash of session file content (for deduplication)
            priority: Task priority (1=highest, higher numbers=lower priority)
            stat_name: Human-readable name for the stat

        Returns:
            Task ID of created task
        """
        # Ensure queue exists
        self._ensure_queue_exists(stat_id, stat_name)

        # Load queue data
        queue_data = self._load_queue_data(stat_id)
        if not queue_data:
            raise ValueError(f"Could not load queue for stat: {stat_id}")

        # Check for duplicate session hash
        if session_hash:
            for task in queue_data.tasks:
                if task.session_hash == session_hash and task.status not in ["failed"]:
                    logger.debug(
                        f"Task already exists for session hash: {session_hash}"
                    )
                    return task.task_id

        # Create new task
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            session_file=session_file,
            session_hash=session_hash or f"file:{Path(session_file).name}",
            status="pending",
            priority=priority,
            created_at=datetime.now().isoformat() + "Z",
        )

        # Add to queue
        queue_data.tasks.append(task)

        # Save queue data
        self._save_queue_data(queue_data)

        logger.info(
            f"Added task {task_id} to queue {stat_id} for session: {Path(session_file).name}"
        )
        return task_id

    def get_next_task_from_stat(self, stat_id: str) -> Optional[Task]:
        """
        Get the next pending task from a stat queue.

        Args:
            stat_id: Stat identifier

        Returns:
            Next task or None if no pending tasks
        """
        queue_data = self._load_queue_data(stat_id)
        if not queue_data:
            return None

        # Find highest priority pending task
        pending_tasks = [task for task in queue_data.tasks if task.status == "pending"]
        if not pending_tasks:
            return None

        # Sort by priority (1 = highest), then by creation time
        pending_tasks.sort(key=lambda t: (t.priority, t.created_at))
        next_task = pending_tasks[0]

        # Mark as processing
        next_task.status = "processing"
        next_task.started_at = datetime.now().isoformat() + "Z"

        # Save updated queue
        self._save_queue_data(queue_data)

        logger.info(f"Retrieved task {next_task.task_id} from queue {stat_id}")
        return next_task

    def complete_task(
        self, stat_id: str, task_id: str, processing_time_ms: int = None
    ) -> bool:
        """
        Mark a task as completed.

        Args:
            stat_id: Stat identifier
            task_id: Task identifier
            processing_time_ms: Processing time in milliseconds

        Returns:
            True if task was marked completed, False otherwise
        """
        queue_data = self._load_queue_data(stat_id)
        if not queue_data:
            return False

        # Find task
        task = None
        for t in queue_data.tasks:
            if t.task_id == task_id:
                task = t
                break

        if not task:
            logger.warning(f"Task not found: {task_id} in queue {stat_id}")
            return False

        # Mark as completed
        task.status = "completed"
        task.completed_at = datetime.now().isoformat() + "Z"
        if processing_time_ms:
            task.processing_time_ms = processing_time_ms

        # Save queue data
        self._save_queue_data(queue_data)

        logger.info(f"Completed task {task_id} in queue {stat_id}")
        return True

    def fail_task(self, stat_id: str, task_id: str, error_message: str) -> bool:
        """
        Mark a task as failed.

        Args:
            stat_id: Stat identifier
            task_id: Task identifier
            error_message: Error description

        Returns:
            True if task was marked failed, False otherwise
        """
        queue_data = self._load_queue_data(stat_id)
        if not queue_data:
            return False

        # Find task
        task = None
        for t in queue_data.tasks:
            if t.task_id == task_id:
                task = t
                break

        if not task:
            logger.warning(f"Task not found: {task_id} in queue {stat_id}")
            return False

        # Mark as failed
        task.status = "failed"
        task.completed_at = datetime.now().isoformat() + "Z"
        task.error_message = error_message
        task.retry_count += 1

        # Move to dead letter queue if max retries exceeded
        if task.retry_count >= task.max_retries:
            queue_data.dead_letter_queue.append(task)
            queue_data.tasks.remove(task)
            logger.warning(
                f"Task {task_id} moved to dead letter queue after {task.retry_count} failures"
            )

        # Save queue data
        self._save_queue_data(queue_data)

        logger.warning(f"Failed task {task_id} in queue {stat_id}: {error_message}")
        return True

    def retry_task(self, stat_id: str, task_id: str) -> bool:
        """
        Retry a failed task.

        Args:
            stat_id: Stat identifier
            task_id: Task identifier

        Returns:
            True if task was reset for retry, False otherwise
        """
        queue_data = self._load_queue_data(stat_id)
        if not queue_data:
            return False

        # Find task
        task = None
        for t in queue_data.tasks:
            if t.task_id == task_id:
                task = t
                break

        if not task or task.status != "failed":
            return False

        # Check if retries available
        if task.retry_count >= task.max_retries:
            logger.warning(f"Cannot retry task {task_id}: max retries exceeded")
            return False

        # Reset to pending
        task.status = "pending"
        task.started_at = None
        task.completed_at = None
        task.error_message = None

        # Save queue data
        self._save_queue_data(queue_data)

        logger.info(f"Reset task {task_id} for retry in queue {stat_id}")
        return True

    def list_active_stats(self) -> List[str]:
        """
        Get list of all active stat IDs.

        Returns:
            List of stat IDs
        """
        index_data = self._read_json_file(self.index_file)
        return [
            queue["stat_id"]
            for queue in index_data.get("queues", [])
            if queue.get("status") == "active"
        ]

    def get_stat_queue_stats(self, stat_id: str) -> Optional[QueueStats]:
        """
        Get statistics for a specific stat queue.

        Args:
            stat_id: Stat identifier

        Returns:
            Queue statistics or None if not found
        """
        queue_data = self._load_queue_data(stat_id)
        return queue_data.stats if queue_data else None

    def get_all_queue_stats(self) -> Dict[str, QueueStats]:
        """
        Get statistics for all queues.

        Returns:
            Dictionary of stat_id -> QueueStats
        """
        stats = {}
        for stat_id in self.list_active_stats():
            stat_stats = self.get_stat_queue_stats(stat_id)
            if stat_stats:
                stats[stat_id] = stat_stats
        return stats


def main():
    """Test the queue manager."""
    import argparse

    parser = argparse.ArgumentParser(description="SportMetrics Queue Manager Test")
    parser.add_argument(
        "--queues-dir", default="backend/src/automation/queues", help="Queues directory"
    )
    parser.add_argument("--test", action="store_true", help="Run test operations")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create queue manager
    qm = QueueManager(args.queues_dir)

    if args.test:
        # Test operations
        print("Testing queue operations...")

        # Add some test tasks
        task1 = qm.add_task_to_stat(
            "running_sessions", "session1.json", "hash1", stat_name="Running Sessions"
        )
        task2 = qm.add_task_to_stat(
            "cycling_sessions", "session2.json", "hash2", stat_name="Cycling Sessions"
        )

        print(f"Created tasks: {task1}, {task2}")

        # Get stats
        stats = qm.get_all_queue_stats()
        for stat_id, stat_stats in stats.items():
            print(f"{stat_id}: {stat_stats}")

        # Get next tasks
        running_task = qm.get_next_task_from_stat("running_sessions")
        if running_task:
            print(f"Next running task: {running_task.task_id}")
            qm.complete_task("running_sessions", running_task.task_id, 5000)

        cycling_task = qm.get_next_task_from_stat("cycling_sessions")
        if cycling_task:
            print(f"Next cycling task: {cycling_task.task_id}")
            qm.fail_task("cycling_sessions", cycling_task.task_id, "Test failure")

    else:
        # Just show current stats
        stats = qm.get_all_queue_stats()
        if stats:
            print("Queue Statistics:")
            for stat_id, stat_stats in stats.items():
                print(f"  {stat_id}: {stat_stats}")
        else:
            print("No active queues found")


if __name__ == "__main__":
    main()
