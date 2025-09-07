#!/usr/bin/env python3
"""
SportMetrics Automation Startup Script

Starts both the file watcher and queue worker processes based on JSON configuration.
"""

import sys
import signal
import time
import logging
import multiprocessing as mp
from pathlib import Path

# Add the parent directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.config_loader import load_config
from automation.file_watcher import FileWatcher
from automation.queue_worker import QueueWorker


logger = logging.getLogger("SportMetrics.Automation")


class AutomationManager:
    """Manages file watcher and queue worker processes."""
    
    def __init__(self, config_file: str = None):
        """
        Initialize automation manager.
        
        Args:
            config_file: Path to configuration file
        """
        self.config = load_config(config_file)
        self.file_watcher_process = None
        self.queue_worker_process = None
        self.shutdown_requested = False
        
        # Set up logging from config
        log_config = self.config.get_logging_config()
        logging.basicConfig(
            level=getattr(logging, log_config.get('level', 'INFO')),
            format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        
        # Create necessary directories
        try:
            self.config.create_directories()
            logger.info("All required directories created successfully")
        except Exception as e:
            logger.error(f"Failed to create required directories: {e}")
            raise
        
        logger.info("AutomationManager initialized with config-based setup")
        logger.info(f"Sessions directory: {self.config.get_sessions_dir()}")
        logger.info(f"Output directory: {self.config.get_output_dir()}")
        logger.info(f"Queues directory: {self.config.get_queues_dir()}")
    
    def _run_file_watcher(self):
        """Run the file watcher in a separate process."""
        try:
            logger.info("Starting file watcher process...")
            
            fw_config = self.config.get_file_watcher_config()
            storage_config = self.config.get_storage_config()
            
            watcher = FileWatcher(
                sessions_dir=fw_config['sessions_dir'],
                poll_interval=fw_config['poll_interval'],
                stability_check_seconds=fw_config['stability_check_seconds'],
                state_file=fw_config['state_file'],
                queues_dir=storage_config['queues_dir'],
                default_stat_configs=fw_config.get('default_stat_configs', [])
            )
            
            watcher.start()
            
        except KeyboardInterrupt:
            logger.info("File watcher received shutdown signal")
        except Exception as e:
            logger.error(f"File watcher failed: {e}")
            raise
    
    def _run_queue_worker(self):
        """Run the queue worker in a separate process."""
        try:
            logger.info("Starting queue worker process...")
            
            qw_config = self.config.get_queue_worker_config()
            storage_config = self.config.get_storage_config()
            
            worker = QueueWorker(
                queues_dir=storage_config['queues_dir'],
                sessions_dir=self.config.get_sessions_dir(),
                output_dir=storage_config['output_dir'],
                poll_interval=qw_config['poll_interval'],
                task_timeout=qw_config.get('task_timeout', 300)
            )
            
            worker.start()
            
        except KeyboardInterrupt:
            logger.info("Queue worker received shutdown signal")
        except Exception as e:
            logger.error(f"Queue worker failed: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_requested = True
        
        if self.file_watcher_process and self.file_watcher_process.is_alive():
            logger.info("Terminating file watcher process...")
            self.file_watcher_process.terminate()
        
        if self.queue_worker_process and self.queue_worker_process.is_alive():
            logger.info("Terminating queue worker process...")
            self.queue_worker_process.terminate()
    
    def start(self):
        """Start both file watcher and queue worker."""
        logger.info("Starting SportMetrics automation services...")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            # Start file watcher process
            self.file_watcher_process = mp.Process(
                target=self._run_file_watcher,
                name="FileWatcher"
            )
            self.file_watcher_process.start()
            logger.info(f"File watcher started with PID: {self.file_watcher_process.pid}")
            
            # Start queue worker process
            self.queue_worker_process = mp.Process(
                target=self._run_queue_worker,
                name="QueueWorker"
            )
            self.queue_worker_process.start()
            logger.info(f"Queue worker started with PID: {self.queue_worker_process.pid}")
            
            # Monitor processes
            self._monitor_processes()
            
        except Exception as e:
            logger.error(f"Failed to start automation services: {e}")
            self.shutdown()
            sys.exit(1)
    
    def _monitor_processes(self):
        """Monitor both processes and handle failures."""
        logger.info("Monitoring automation processes...")
        
        monitoring_config = self.config.get_monitoring_config()
        health_check_interval = monitoring_config.get('health_check_interval', 30)
        
        while not self.shutdown_requested:
            try:
                time.sleep(health_check_interval)
                
                # Check if processes are still alive
                if not self.file_watcher_process.is_alive():
                    if not self.shutdown_requested:
                        logger.error("File watcher process died unexpectedly!")
                        self.shutdown_requested = True
                
                if not self.queue_worker_process.is_alive():
                    if not self.shutdown_requested:
                        logger.error("Queue worker process died unexpectedly!")
                        self.shutdown_requested = True
                
                if self.shutdown_requested:
                    break
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt, shutting down...")
                self.shutdown_requested = True
                break
        
        self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown all processes."""
        logger.info("Shutting down automation services...")
        
        # Wait for processes to finish gracefully
        processes_to_wait = []
        
        if self.file_watcher_process and self.file_watcher_process.is_alive():
            logger.info("Waiting for file watcher to finish...")
            processes_to_wait.append(self.file_watcher_process)
        
        if self.queue_worker_process and self.queue_worker_process.is_alive():
            logger.info("Waiting for queue worker to finish...")
            processes_to_wait.append(self.queue_worker_process)
        
        # Give processes 10 seconds to shutdown gracefully
        for process in processes_to_wait:
            process.join(timeout=10)
            if process.is_alive():
                logger.warning(f"Force killing process {process.name}...")
                process.kill()
                process.join()
        
        logger.info("All automation services stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SportMetrics Automation Services")
    parser.add_argument(
        "--config",
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit"
    )
    
    args = parser.parse_args()
    
    try:
        # Load and optionally validate config
        config = load_config(args.config)
        
        if args.validate_config:
            print("✅ Configuration is valid")
            print(f"📁 Sessions directory: {config.get_sessions_dir()}")
            print(f"📁 Output directory: {config.get_output_dir()}")
            print(f"📁 Queues directory: {config.get_queues_dir()}")
            print(f"📊 Log level: {config.get_log_level()}")
            return 0
        
        # Create and start automation manager
        manager = AutomationManager(args.config)
        manager.start()
        
    except Exception as e:
        print(f"❌ Automation services failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())