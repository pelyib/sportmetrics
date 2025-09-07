#!/usr/bin/env python3
"""
SportMetrics Queue Worker

Processes tasks from all stat queues in round-robin fashion by executing session_processor.py
"""

import time
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .queue_manager import QueueManager

logger = logging.getLogger("SportMetrics.QueueWorker")


class QueueWorker:
    """Worker that processes tasks from all stat queues."""
    
    def __init__(
        self,
        queues_dir: str,
        sessions_dir: str,
        output_dir: str,
        poll_interval: int = 3,
        task_timeout: int = 300
    ):
        """
        Initialize the queue worker.
        
        Args:
            queues_dir: Directory containing queue files
            sessions_dir: Directory containing session JSON files  
            output_dir: Directory for processed output files
            poll_interval: Seconds between queue polls
            task_timeout: Maximum time for task execution in seconds
        """
        self.queues_dir = Path(queues_dir)
        self.sessions_dir = Path(sessions_dir)
        self.output_dir = Path(output_dir)
        self.poll_interval = poll_interval
        self.task_timeout = task_timeout
        self.running = False
        
        # Initialize queue manager
        self.queue_manager = QueueManager(str(queues_dir))
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"QueueWorker initialized")
        logger.info(f"Queues directory: {self.queues_dir}")
        logger.info(f"Sessions directory: {self.sessions_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Task timeout: {self.task_timeout} seconds")
    
    def start(self):
        """Start the queue worker."""
        logger.info("Starting queue worker...")
        self.running = True
        
        try:
            while self.running:
                self._process_next_task()
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the queue worker."""
        if self.running:
            logger.info("Stopping queue worker...")
            self.running = False
            logger.info("Queue worker stopped")
    
    def _process_next_task(self):
        """Process the next available task from any queue (round-robin)."""
        try:
            # Get all active stat queues
            active_stats = self.queue_manager.list_active_stats()
            
            if not active_stats:
                logger.debug("No active stat queues found")
                return
            
            # Round-robin through stat queues looking for pending tasks
            for stat_id in active_stats:
                task = self.queue_manager.get_next_task_from_stat(stat_id)
                if task:
                    logger.info(f"Processing task {task.task_id} from queue {stat_id}")
                    success = self._execute_task(stat_id, task)
                    
                    if success:
                        self._complete_task(stat_id, task)
                    else:
                        self._fail_task(stat_id, task)
                    
                    # Only process one task at a time
                    return
            
            # No tasks found in any queue
            logger.debug("No pending tasks found in any queue")
            
        except Exception as e:
            logger.error(f"Error processing tasks: {e}")
    
    def _execute_task(self, stat_id: str, task) -> bool:
        """
        Execute a task by running session_processor.py with stat-specific parameters.
        
        Args:
            stat_id: Stat identifier
            task: Task to execute
            
        Returns:
            True if task executed successfully, False otherwise
        """
        try:
            start_time = datetime.now()
            
            # Generate output filename based on stat_id
            output_file = self.output_dir / f"{stat_id}_chart_data.json"
            
            # Build command for session processor
            processor_path = Path(__file__).parent.parent / "session_processor.py"
            cmd = [
                sys.executable,
                str(processor_path),
                "--sessions-dir", str(self.sessions_dir),
                "--output", str(output_file)
            ]
            
            # Add stat-specific filters based on stat_id
            cmd.extend(self._get_stat_filters(stat_id))
            
            logger.debug(f"Executing command: {' '.join(cmd)}")
            
            # Execute the command
            result = subprocess.run(
                cmd,
                timeout=self.task_timeout,
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            end_time = datetime.now()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            if result.returncode == 0:
                logger.info(f"Task {task.task_id} completed successfully in {processing_time_ms}ms")
                logger.debug(f"Command output: {result.stdout}")
                
                # Store processing time for completion
                task.processing_time_ms = processing_time_ms
                return True
            else:
                logger.error(f"Task {task.task_id} failed with return code {result.returncode}")
                logger.error(f"Command stderr: {result.stderr}")
                
                # Store error message for failure handling
                task.error_message = f"Process failed: {result.stderr}"
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Task {task.task_id} timed out after {self.task_timeout} seconds")
            task.error_message = f"Task timed out after {self.task_timeout} seconds"
            return False
            
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            task.error_message = str(e)
            return False
    
    def _get_stat_filters(self, stat_id: str) -> List[str]:
        """
        Get command-line filters for a specific stat type.
        
        Args:
            stat_id: Stat identifier
            
        Returns:
            List of command-line arguments for filtering
        """
        filters = []
        
        if stat_id == "running_sessions":
            filters.extend(["--sport", "RUNNING"])
        elif stat_id == "cycling_sessions":
            filters.extend(["--sport", "CYCLING"])
        elif stat_id == "long_distance":
            filters.extend(["--min-distance", "20000"])  # 20km in meters
        elif stat_id == "all_sessions":
            # No filters for all sessions
            pass
        else:
            # Custom stat - no specific filters for now
            logger.debug(f"No specific filters defined for stat_id: {stat_id}")
        
        return filters
    
    def _complete_task(self, stat_id: str, task):
        """Mark a task as completed."""
        try:
            success = self.queue_manager.complete_task(
                stat_id, 
                task.task_id, 
                getattr(task, 'processing_time_ms', None)
            )
            
            if success:
                logger.info(f"Marked task {task.task_id} as completed")
            else:
                logger.warning(f"Failed to mark task {task.task_id} as completed")
                
        except Exception as e:
            logger.error(f"Error completing task {task.task_id}: {e}")
    
    def _fail_task(self, stat_id: str, task):
        """Mark a task as failed."""
        try:
            error_message = getattr(task, 'error_message', 'Unknown error')
            success = self.queue_manager.fail_task(
                stat_id,
                task.task_id,
                error_message
            )
            
            if success:
                logger.warning(f"Marked task {task.task_id} as failed: {error_message}")
            else:
                logger.error(f"Failed to mark task {task.task_id} as failed")
                
        except Exception as e:
            logger.error(f"Error failing task {task.task_id}: {e}")


def main():
    """Main entry point for testing the queue worker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SportMetrics Queue Worker")
    parser.add_argument(
        "--queues-dir", 
        default="backend/src/automation/queues", 
        help="Queues directory"
    )
    parser.add_argument(
        "--sessions-dir",
        default="sessions",
        help="Sessions directory"
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=3,
        help="Poll interval in seconds"
    )
    parser.add_argument(
        "--task-timeout",
        type=int,
        default=300,
        help="Task timeout in seconds"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and start worker
    worker = QueueWorker(
        queues_dir=args.queues_dir,
        sessions_dir=args.sessions_dir,
        output_dir=args.output_dir,
        poll_interval=args.poll_interval,
        task_timeout=args.task_timeout
    )
    
    try:
        worker.start()
    except Exception as e:
        logger.error(f"Queue worker failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())