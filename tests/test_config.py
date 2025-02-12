"""Tests for configuration functionality."""
import pytest
from pathlib import Path
import tomli_w
from datetime import datetime

from gitsmartcommit.config import Config

def test_default_config():
    """Test default configuration values."""
    config = Config()
    assert config.main_branch == "main"
    assert config.commit_style == "conventional"
    assert config.remote_name == "origin"
    assert config.auto_push is False
    assert config.always_log is False
    assert config.log_file is None

def test_config_load_nonexistent(tmp_path):
    """Test loading configuration when file doesn't exist."""
    config = Config.load(tmp_path)
    assert config.main_branch == "main"  # Should use defaults

def test_config_load_and_save(tmp_path):
    """Test saving and loading configuration."""
    # Create a config with non-default values
    config = Config(
        main_branch="develop",
        commit_style="simple",
        remote_name="upstream",
        auto_push=True,
        always_log=True,
        log_file="custom.log"
    )
    
    # Save it
    config.save(tmp_path)
    
    # Load it back
    loaded_config = Config.load(tmp_path)
    
    # Verify values
    assert loaded_config.main_branch == "develop"
    assert loaded_config.commit_style == "simple"
    assert loaded_config.remote_name == "upstream"
    assert loaded_config.auto_push is True
    assert loaded_config.always_log is True
    assert loaded_config.log_file == "custom.log"

def test_config_load_invalid(tmp_path):
    """Test loading invalid configuration file."""
    config_path = tmp_path / ".gitsmartcommit.toml"
    
    # Write invalid TOML
    config_path.write_text("invalid [ toml")
    
    # Should get default config
    config = Config.load(tmp_path)
    assert config.main_branch == "main"

def test_get_log_file_disabled():
    """Test get_log_file when logging is disabled."""
    config = Config(always_log=False, log_file=None)
    assert config.get_log_file() is None

def test_get_log_file_custom():
    """Test get_log_file with custom log file."""
    config = Config(always_log=False, log_file="custom.log")
    assert config.get_log_file() == Path("custom.log")

def test_get_log_file_always():
    """Test get_log_file with always_log enabled."""
    config = Config(always_log=True)
    log_file = config.get_log_file()
    
    assert log_file is not None
    assert log_file.name.startswith("gsc_log-")
    assert log_file.suffix == ".log"
    
    # Verify timestamp format
    timestamp_str = log_file.stem.split("-", 1)[1]
    try:
        datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        pytest.fail("Invalid timestamp format in log filename") 