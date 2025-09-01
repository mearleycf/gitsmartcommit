"""Configuration management for git-smart-commit."""
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import tomli
import tomli_w
import os
import re

DEFAULT_CONFIG_FILENAME = ".gitsmartcommit.toml"

class Config(BaseModel):
    """Configuration settings for git-smart-commit.
    
    This class defines all configurable options that can be set either
    via the config file or command line arguments.
    """
    
    main_branch: str = Field(
        default="main",
        description="Name of the main branch to merge into"
    )
    
    commit_style: str = Field(
        default="conventional",
        description="Style of commit messages to generate (conventional or simple)"
    )
    
    remote_name: str = Field(
        default="origin",
        description="Name of the remote repository (e.g., origin, upstream)"
    )
    
    auto_push: bool = Field(
        default=False,
        description="Whether to automatically push changes after committing"
    )
    
    always_log: bool = Field(
        default=False,
        description="Whether to always generate log files"
    )
    
    log_file: Optional[str] = Field(
        default=None,
        description="Path to log file (if not using automatic log file generation)"
    )

    model: str = Field(
        default="qwen2.5-coder:7b",
        description="AI model to use for generating commit messages (e.g., claude-3-5-sonnet-latest, gemini-pro, qwen2.5-coder:7b)"
    )
    
    def _sanitize_string(self, value: str) -> str:
        """Sanitize string values to prevent injection attacks."""
        if not value:
            return value
        
        # Remove control characters and null bytes
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        # Remove command injection patterns and split on them
        value = re.split(r'[;&|`$()]', value)[0]
        
        # Limit length
        if len(value) > 1000:
            value = value[:1000]
        
        return value.strip()
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if a path is safe (no path traversal)."""
        if not path:
            return False
        
        # Check for path traversal patterns
        if '..' in path or path.startswith('/') or '\\' in path:
            return False
        
        # Check for absolute paths
        if os.path.isabs(path):
            return False
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'/etc/', r'/var/', r'/usr/', r'/bin/', r'/sbin/',
            r'C:\\Windows', r'C:\\System', r'C:\\Program'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return False
        
        return True

    @classmethod
    def load(cls, repo_path: Path) -> 'Config':
        """Load configuration from the config file.
        
        Args:
            repo_path: Path to the git repository
            
        Returns:
            Config: Configuration object with values from file or defaults
        """
        config_path = repo_path / DEFAULT_CONFIG_FILENAME
        
        if not config_path.exists():
            return cls()
        
        try:
            with config_path.open('rb') as f:
                config_data = tomli.load(f)
            
            # Sanitize config data
            if 'gitsmartcommit' in config_data:
                config_section = config_data['gitsmartcommit']
                
                # Sanitize string values
                for key in ['main_branch', 'commit_style', 'remote_name', 'log_file', 'model']:
                    if key in config_section and isinstance(config_section[key], str):
                        config_section[key] = cls._sanitize_string(config_section[key])
                
                # Validate log_file path
                if 'log_file' in config_section and config_section['log_file']:
                    if not cls._is_safe_path(config_section['log_file']):
                        print(f"Warning: Unsafe log file path '{config_section['log_file']}', using default")
                        config_section['log_file'] = None
            
            return cls(**config_data)
        except Exception as e:
            # If there's any error reading the config, use defaults
            print(f"Warning: Error reading config file: {e}")
            return cls()
    
    def save(self, repo_path: Path) -> None:
        """Save configuration to the config file.
        
        Args:
            repo_path: Path to the git repository
        """
        config_path = repo_path / DEFAULT_CONFIG_FILENAME
        
        try:
            # Convert to dict and remove None values
            config_dict = {k: v for k, v in self.model_dump().items() if v is not None}
            
            # Validate paths before saving
            if 'log_file' in config_dict and config_dict['log_file']:
                if not self._is_safe_path(config_dict['log_file']):
                    print(f"Warning: Unsafe log file path '{config_dict['log_file']}', not saving")
                    config_dict['log_file'] = None
            
            with config_path.open('wb') as f:
                tomli_w.dump(config_dict, f)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get_log_file(self) -> Optional[Path]:
        """Get the path to the log file.
        
        If always_log is True, generates a timestamped log file name.
        Otherwise, returns the configured log_file path if set.
        
        Returns:
            Optional[Path]: Path to the log file, or None if logging is disabled
        """
        if self.always_log:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            return Path(f"gsc_log-{timestamp}.log")
        elif self.log_file:
            # Validate the log file path
            if self._is_safe_path(self.log_file):
                return Path(self.log_file)
            else:
                print(f"Warning: Unsafe log file path '{self.log_file}', using default")
                return None
        return None

    def __init__(self, **data):
        """Initialize config with environment variable support and sanitization."""
        # Load from environment variables first
        env_data = {}
        
        # Map environment variables to config fields
        env_mapping = {
            'GIT_SMART_COMMIT_MAIN_BRANCH': 'main_branch',
            'GIT_SMART_COMMIT_COMMIT_STYLE': 'commit_style',
            'GIT_SMART_COMMIT_REMOTE_NAME': 'remote_name',
            'GIT_SMART_COMMIT_AUTO_PUSH': 'auto_push',
            'GIT_SMART_COMMIT_ALWAYS_LOG': 'always_log',
            'GIT_SMART_COMMIT_LOG_FILE': 'log_file',
            'GIT_SMART_COMMIT_MODEL': 'model'
        }
        
        for env_var, field_name in env_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                
                # Sanitize string values
                if field_name in ['main_branch', 'commit_style', 'remote_name', 'log_file', 'model']:
                    value = self._sanitize_string(value)
                
                # Convert boolean values
                if field_name in ['auto_push', 'always_log']:
                    value = value.lower() in ['true', '1', 'yes', 'on']
                
                env_data[field_name] = value
        
        # Merge with provided data
        merged_data = {**env_data, **data}
        
        super().__init__(**merged_data) 