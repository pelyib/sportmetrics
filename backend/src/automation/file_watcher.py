#!/usr/bin/env python3
"""
SportMetrics File Watcher

Monitors the sessions directory for new .json files using simple directory polling.
Tracks the last processed file to efficiently skip already processed files.
"""

import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict
from .queue_manager import QueueManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SportMetrics.FileWatcher")


class FileWatcher:
    """Simple file watcher using directory polling with last file tracking."""

    def __init__(
        self,
        sessions_dir: str = "sessions",
        poll_interval: int = 5,
        stability_check_seconds: int = 2,
        state_file: str = "backend/src/automation/last_processed.txt",
        queues_dir: str = "backend/src/automation/queues",
        default_stat_configs: List[Dict[str, any]] = None,
    ):
        """
        Initialize the file watcher.

        Args:
            sessions_dir: Directory to monitor for session files
            poll_interval: Seconds between directory scans
            stability_check_seconds: Seconds to wait before considering file write complete
            state_file: Path to file for tracking last processed session file
            queues_dir: Directory containing queue files
            default_stat_configs: List of default stat configurations to create tasks for
        """
        self.sessions_dir = Path(sessions_dir).resolve()
        self.poll_interval = poll_interval
        self.stability_check_seconds = stability_check_seconds
        self.last_processed_file: Optional[str] = None
        self.running = False

        # State file for tracking last processed file
        self.state_file = Path(state_file).resolve()
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Queue manager for creating tasks
        self.queue_manager = QueueManager(queues_dir)

        # Default stat configurations
        if default_stat_configs is None:
            self.default_stat_configs = [
                {"stat_id": "all_sessions", "stat_name": "All Sessions", "priority": 3},
                {
                    "stat_id": "running_sessions",
                    "stat_name": "Running Sessions",
                    "priority": 1,
                },
                {
                    "stat_id": "cycling_sessions",
                    "stat_name": "Cycling Sessions",
                    "priority": 1,
                },
                {
                    "stat_id": "long_distance",
                    "stat_name": "Long Distance (20km+)",
                    "priority": 2,
                },
            ]
        else:
            self.default_stat_configs = default_stat_configs

        # Ensure sessions directory exists
        self.sessions_dir.mkdir(exist_ok=True)

        # Load last processed file from state file
        self._load_state()

        logger.info(f"FileWatcher initialized for directory: {self.sessions_dir}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Stability check: {self.stability_check_seconds} seconds")
        logger.info(
            f"Default stat configs: {[cfg['stat_id'] for cfg in self.default_stat_configs]}"
        )
        if self.last_processed_file:
            logger.info(f"Will resume after: {self.last_processed_file}")

    def _load_state(self):
        """Load the last processed file from state file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.last_processed_file = f.read().strip()
                if self.last_processed_file:
                    logger.info(
                        f"Loaded last processed file: {self.last_processed_file}"
                    )
        except Exception as e:
            logger.warning(f"Could not load state file: {e}")
            self.last_processed_file = None

    def _save_state(self):
        """Save the last processed file to state file."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                f.write(self.last_processed_file or "")
        except Exception as e:
            logger.error(f"Could not save state file: {e}")

    def start(self):
        """Start the file watcher."""
        logger.info("Starting file watcher...")
        self.running = True

        try:
            while self.running:
                self._scan_directory()
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping...")
        finally:
            self.stop()

    def stop(self):
        """Stop the file watcher."""
        if self.running:
            logger.info("Stopping file watcher...")
            self.running = False
            self._save_state()
            logger.info("File watcher stopped")

    def _scan_directory(self):
        """Scan the sessions directory for new files."""
        try:
            # List all .json files in sorted order
            all_files = sorted(self.sessions_dir.glob("*.json"))

            if not all_files:
                logger.debug("No .json files found in sessions directory")
                return

            # Find files to process (after last processed)
            files_to_check = []

            if self.last_processed_file:
                # Only check files that come after the last processed one
                files_to_check = [
                    f for f in all_files if f.name > self.last_processed_file
                ]
            else:
                # First run - check all files
                files_to_check = all_files

            if not files_to_check:
                logger.debug("No new files to process")
                return

            logger.info(f"Found {len(files_to_check)} new files to check")

            # Check which files are stable and ready for batch processing
            stable_files = []
            for file_path in files_to_check:
                if self._is_session_file(file_path):
                    if self._is_file_stable(file_path):
                        stable_files.append(file_path)
                    else:
                        logger.debug(f"File not stable yet: {file_path.name}")
                        # Don't include unstable files in this batch
                        break
                else:
                    logger.debug(f"Skipping non-session file: {file_path.name}")
                    # Still update last processed to skip this file next time
                    self.last_processed_file = file_path.name
                    self._save_state()

            # Process stable files in batch
            if stable_files:
                self._process_session_files_batch(stable_files)

        except Exception as e:
            logger.error(f"Error scanning directory: {e}")

    def _is_session_file(self, file_path: Path) -> bool:
        """
        Check if the file is a session JSON file we should process.

        Args:
            file_path: Path to the file

        Returns:
            True if file should be processed, False otherwise
        """
        # Check extension (already filtered by glob, but double-check)
        if file_path.suffix.lower() != ".json":
            return False

        # Ignore hidden files and temporary files
        if (
            file_path.name.startswith(".")
            or file_path.name.endswith("~")
            or ".tmp" in file_path.name
        ):
            logger.debug(f"Ignoring file: {file_path.name} (hidden/temporary)")
            return False

        return True

    def _is_file_stable(self, file_path: Path) -> bool:
        """
        Check if file is stable (not being written to).

        Args:
            file_path: Path to the file

        Returns:
            True if file appears stable and ready for processing
        """
        try:
            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return False

            # Get initial file stats
            stat1 = file_path.stat()

            # Check if file has content
            if stat1.st_size == 0:
                logger.debug(f"File has no content yet: {file_path.name}")
                return False

            # Wait for stability check period
            time.sleep(self.stability_check_seconds)

            # Check if file still exists (might have been deleted/moved)
            if not file_path.exists():
                logger.debug(
                    f"File disappeared during stability check: {file_path.name}"
                )
                return False

            # Get stats after waiting
            stat2 = file_path.stat()

            # Check if size and modification time are unchanged
            if stat1.st_size != stat2.st_size or stat1.st_mtime != stat2.st_mtime:
                logger.debug(f"File still being modified: {file_path.name}")
                return False

            # Quick JSON validity check
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    # Try to read first few characters to see if it looks like JSON
                    first_chars = f.read(10)
                    if not first_chars.strip().startswith("{"):
                        logger.debug(
                            f"File doesn't appear to be valid JSON: {file_path.name}"
                        )
                        return False
            except (IOError, OSError) as e:
                logger.debug(f"Cannot read file: {file_path.name} - {e}")
                return False

            return True

        except (OSError, IOError) as e:
            logger.debug(f"Error checking file stability: {file_path.name} - {e}")
            return False

    def _process_session_files_batch(self, file_paths: List[Path]):
        """
        Process a batch of session files by creating tasks for all configured stats.

        Args:
            file_paths: List of file paths to process
        """
        try:
            logger.info(f"Processing batch of {len(file_paths)} session files")

            for file_path in file_paths:
                try:
                    self._process_single_session_file(file_path)

                    # Update last processed file
                    self.last_processed_file = file_path.name
                    self._save_state()

                except Exception as e:
                    logger.error(f"Error processing session file {file_path}: {e}")
                    # Continue processing other files in batch
                    continue

            logger.info(f"Completed processing batch of {len(file_paths)} files")

        except Exception as e:
            logger.error(f"Error processing session files batch: {e}")

    def _process_single_session_file(self, file_path: Path):
        """
        Process a single session file by creating tasks for all configured stats.

        Args:
            file_path: Path to the session file
        """
        logger.info(f"Processing session file: {file_path.name}")

        # Calculate file hash for deduplication
        session_hash = self._calculate_file_hash(file_path)

        # Get relative path for consistent task creation
        try:
            relative_path = file_path.relative_to(Path.cwd())
        except ValueError:
            # If not relative to current directory, use absolute path
            relative_path = file_path

        session_file_str = str(relative_path)

        # Create tasks for all configured stats
        created_tasks = []
        for stat_config in self.default_stat_configs:
            try:
                task_id = self.queue_manager.add_task_to_stat(
                    stat_id=stat_config["stat_id"],
                    session_file=session_file_str,
                    session_hash=session_hash,
                    priority=stat_config.get("priority", 1),
                    stat_name=stat_config.get("stat_name"),
                )
                created_tasks.append(f"{stat_config['stat_id']}:{task_id}")

            except Exception as e:
                logger.error(f"Failed to create task for {stat_config['stat_id']}: {e}")
                continue

        if created_tasks:
            logger.info(f"Created {len(created_tasks)} tasks for {file_path.name}")
            logger.debug(f"Task IDs: {created_tasks}")
        else:
            logger.warning(f"No tasks created for {file_path.name}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of file content for deduplication.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string
        """
        try:
            hasher = hashlib.sha256()

            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)

            return hasher.hexdigest()

        except Exception as e:
            logger.warning(f"Could not calculate hash for {file_path}: {e}")
            # Fallback to filename + size + mtime
            stat = file_path.stat()
            fallback = f"fallback:{file_path.name}:{stat.st_size}:{stat.st_mtime}"
            return hashlib.sha256(fallback.encode()).hexdigest()

    def get_queue_statistics(self) -> Dict[str, any]:
        """
        Get current statistics from all queues.

        Returns:
            Dictionary with queue statistics
        """
        try:
            return self.queue_manager.get_all_queue_stats()
        except Exception as e:
            logger.error(f"Error getting queue statistics: {e}")
            return {}


def main():
    """Main entry point for the file watcher."""
    import argparse

    parser = argparse.ArgumentParser(description="SportMetrics File Watcher")
    parser.add_argument(
        "--sessions-dir",
        default="sessions",
        help="Directory to monitor for session files (default: sessions)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Seconds between directory scans (default: 5)",
    )
    parser.add_argument(
        "--stability-check",
        type=int,
        default=2,
        help="Seconds to wait before considering file write complete (default: 2)",
    )
    parser.add_argument(
        "--state-file",
        default="backend/src/automation/last_processed.txt",
        help="Path to state file for tracking last processed file (default: backend/src/automation/last_processed.txt)",
    )
    parser.add_argument(
        "--queues-dir",
        default="backend/src/automation/queues",
        help="Directory containing queue files (default: backend/src/automation/queues)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create and start file watcher
    watcher = FileWatcher(
        sessions_dir=args.sessions_dir,
        poll_interval=args.poll_interval,
        stability_check_seconds=args.stability_check,
        state_file=args.state_file,
        queues_dir=args.queues_dir,
    )

    try:
        watcher.start()
    except Exception as e:
        logger.error(f"File watcher failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
