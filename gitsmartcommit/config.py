"""Configuration management for git-smart-commit."""
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import tomli
import tomli_w

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
        default=True,
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
            return Path(self.log_file)
        return None 