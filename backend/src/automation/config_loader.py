#!/usr/bin/env python3
"""
Configuration loader for SportMetrics automation services.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("SportMetrics.Config")


class ConfigLoader:
    """Loads and validates configuration from JSON file."""
    
    def __init__(self, config_file: str = None):
        """
        Initialize config loader.
        
        Args:
            config_file: Path to config JSON file. If None, uses default location.
        """
        if config_file is None:
            config_file = Path(__file__).parent / "automation_config.json"
        
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            if not self.config_file.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_file}")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            logger.info(f"Loaded configuration from: {self.config_file}")
            return config
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {self.config_file}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load config file {self.config_file}: {e}")
    
    def _validate_config(self):
        """Validate configuration structure."""
        required_sections = ['file_watcher', 'queue_worker', 'storage', 'logging']
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required config section: {section}")
        
        # Validate file_watcher section
        fw_config = self.config['file_watcher']
        required_fw_keys = ['sessions_dir', 'poll_interval', 'stability_check_seconds', 'state_file']
        for key in required_fw_keys:
            if key not in fw_config:
                raise ValueError(f"Missing required file_watcher config key: {key}")
        
        # Validate queue_worker section
        qw_config = self.config['queue_worker']
        required_qw_keys = ['poll_interval', 'max_concurrent_tasks', 'task_timeout']
        for key in required_qw_keys:
            if key not in qw_config:
                raise ValueError(f"Missing required queue_worker config key: {key}")
        
        # Validate storage section
        storage_config = self.config['storage']
        required_storage_keys = ['queues_dir', 'output_dir']
        for key in required_storage_keys:
            if key not in storage_config:
                raise ValueError(f"Missing required storage config key: {key}")
        
        logger.debug("Configuration validation passed")
    
    def get_file_watcher_config(self) -> Dict[str, Any]:
        """Get file watcher configuration."""
        return self.config['file_watcher'].copy()
    
    def get_queue_worker_config(self) -> Dict[str, Any]:
        """Get queue worker configuration."""
        return self.config['queue_worker'].copy()
    
    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration."""
        return self.config['storage'].copy()
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config['logging'].copy()
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration."""
        return self.config.get('monitoring', {})
    
    def get_sessions_dir(self) -> str:
        """Get sessions directory path."""
        return self.config['file_watcher']['sessions_dir']
    
    def get_output_dir(self) -> str:
        """Get output directory path."""
        return self.config['storage']['output_dir']
    
    def get_queues_dir(self) -> str:
        """Get queues directory path."""
        return self.config['storage']['queues_dir']
    
    def get_log_level(self) -> str:
        """Get logging level."""
        return self.config['logging'].get('level', 'INFO')
    
    def save_config(self, config_file: str = None):
        """Save current configuration to file."""
        if config_file is None:
            config_file = self.config_file
        else:
            config_file = Path(config_file)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"Configuration saved to: {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_file}: {e}")
            raise
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values."""
        def deep_update(base_dict, update_dict):
            """Recursively update nested dictionary."""
            for key, value in update_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self.config, updates)
        self._validate_config()
        logger.info("Configuration updated")
    
    def create_directories(self):
        """Create necessary directories based on configuration."""
        directories = [
            self.get_sessions_dir(),
            self.get_output_dir(), 
            self.get_queues_dir(),
            Path(self.config['file_watcher']['state_file']).parent
        ]
        
        for dir_path in directories:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                logger.info(f"Ensured directory exists: {dir_path}")
            except Exception as e:
                logger.error(f"Could not create directory {dir_path}: {e}")
                raise


def load_config(config_file: str = None) -> ConfigLoader:
    """
    Convenience function to load configuration.
    
    Args:
        config_file: Path to config file, uses default if None
        
    Returns:
        ConfigLoader instance
    """
    return ConfigLoader(config_file)