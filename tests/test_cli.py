"""Tests for CLI functionality."""
import pytest
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, call
from click.testing import CliRunner
from gitsmartcommit.cli import main
from gitsmartcommit.core import CommitUnit, CommitType
from gitsmartcommit.observers import FileLogObserver
from gitsmartcommit.config import Config
from git import Repo
import os

@pytest.fixture
def cli_runner():
    """Fixture for testing CLI commands."""
    return CliRunner()

@pytest.fixture
def mock_analyzer():
    """Mock for ChangeAnalyzer."""
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock:
        analyzer_instance = Mock()
        analyzer_instance.analyze_changes = AsyncMock(return_value=[
            CommitUnit(
                type=CommitType.FEAT,
                scope="test",
                description="test commit",
                files=["test.txt"],
                body="Test commit body",
                message="feat(test): test commit"
            )
        ])
        mock.return_value = analyzer_instance
        yield mock

@pytest.fixture
def mock_committer():
    """Mock for GitCommitter."""
    with patch('gitsmartcommit.cli.GitCommitter') as mock:
        committer_instance = Mock()
        committer_instance.commit_changes = AsyncMock(return_value=True)
        committer_instance.push_changes = AsyncMock(return_value=True)
        committer_instance.merge_to_main = AsyncMock(return_value=True)
        committer_instance.set_upstream = AsyncMock(return_value=True)
        committer_instance.add_observer = Mock()
        mock.return_value = committer_instance
        yield mock

@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository."""
    repo = Repo.init(tmp_path)
    # Create initial commit to avoid issues with first-time repos
    test_file = tmp_path / "test.txt"
    test_file.write_text("Initial content")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")
    return tmp_path

def test_config_dir_flag_creates_config(cli_runner, tmp_path):
    """Test that --config-dir creates a config file if it doesn't exist."""
    with patch('pyperclip.copy') as mock_copy:
        with cli_runner.isolated_filesystem(temp_dir=tmp_path) as td:
            config_path = Path(td) / ".gitsmartcommit.toml"
            assert not config_path.exists()  # Verify file doesn't exist initially
            
            result = cli_runner.invoke(main, ['--config-dir'])
            
            # Verify command succeeded
            assert result.exit_code == 0
            
            # Verify file was created
            assert config_path.exists()
            assert "Created new config file with default values" in result.output
            
            # Verify file contains default values
            config = Config.load(Path(td))
            assert config.main_branch == "main"
            assert config.commit_style == "conventional"
            assert config.remote_name == "origin"
            assert config.auto_push is False
            assert config.always_log is False
            assert config.log_file is None
            
            # Verify path was copied to clipboard
            mock_copy.assert_called_once_with(str(config_path))
            assert "Path copied to clipboard!" in result.output

def test_config_dir_flag_existing_config(cli_runner, tmp_path):
    """Test that --config-dir doesn't overwrite existing config."""
    with patch('pyperclip.copy') as mock_copy:
        with cli_runner.isolated_filesystem(temp_dir=tmp_path) as td:
            # Create config with non-default values
            config_path = Path(td) / ".gitsmartcommit.toml"
            config = Config(
                main_branch="develop",
                commit_style="simple",
                remote_name="upstream"
            )
            config.save(Path(td))
            
            result = cli_runner.invoke(main, ['--config-dir'])
            
            # Verify command succeeded
            assert result.exit_code == 0
            
            # Verify file wasn't modified
            loaded_config = Config.load(Path(td))
            assert loaded_config.main_branch == "develop"
            assert loaded_config.commit_style == "simple"
            assert loaded_config.remote_name == "upstream"
            
            # Verify no creation message
            assert "Created new config file" not in result.output
            
            # Verify path was copied to clipboard
            mock_copy.assert_called_once_with(str(config_path))
            assert "Path copied to clipboard!" in result.output

def test_config_dir_with_custom_path(cli_runner, tmp_path):
    """Test the --config-dir flag with a custom repository path."""
    with patch('pyperclip.copy') as mock_copy:
        repo_path = tmp_path / "custom" / "repo"
        repo_path.mkdir(parents=True)
        
        result = cli_runner.invoke(main, ['--config-dir', '--path', str(repo_path)])
        
        assert result.exit_code == 0
        expected_path = repo_path / ".gitsmartcommit.toml"
        assert str(expected_path) in result.output.replace('\n', '')
        mock_copy.assert_called_once_with(str(expected_path))
        assert "Path copied to clipboard!" in result.output

def test_dry_run(cli_runner, git_repo, mock_analyzer, mock_committer):
    """Test the --dry-run flag."""
    result = cli_runner.invoke(main, ['--dry-run', '--path', str(git_repo)])
    
    assert result.exit_code == 0
    assert "feat(test): test commit" in result.output
    mock_committer.return_value.commit_changes.assert_not_called()
    mock_committer.return_value.push_changes.assert_not_called()

def test_auto_push(cli_runner, git_repo, mock_analyzer, mock_committer):
    """Test the --auto-push flag."""
    result = cli_runner.invoke(main, ['--auto-push', '--path', str(git_repo)])
    
    assert result.exit_code == 0
    mock_committer.return_value.commit_changes.assert_called_once()
    mock_committer.return_value.push_changes.assert_called_once()
    mock_committer.return_value.merge_to_main.assert_not_called()

def test_merge_flag(cli_runner, git_repo, mock_analyzer, mock_committer):
    """Test the --merge flag with auto-push."""
    result = cli_runner.invoke(main, ['--auto-push', '--merge', '--path', str(git_repo)])
    
    assert result.exit_code == 0
    mock_committer.return_value.commit_changes.assert_called_once()
    mock_committer.return_value.push_changes.assert_called_once()
    mock_committer.return_value.merge_to_main.assert_called_once()

def test_main_branch_option(cli_runner, git_repo, mock_analyzer, mock_committer):
    """Test the --main-branch option."""
    result = cli_runner.invoke(main, [
        '--auto-push', '--merge', '--main-branch', 'develop',
        '--path', str(git_repo)
    ])
    
    assert result.exit_code == 0
    mock_committer.return_value.merge_to_main.assert_called_once_with('develop')

def test_commit_style_option(cli_runner, git_repo, mock_analyzer):
    """Test the --commit-style option."""
    # Test conventional style
    result = cli_runner.invoke(main, [
        '--commit-style', 'conventional',
        '--path', str(git_repo)
    ])
    assert result.exit_code == 0
    
    # Test simple style
    result = cli_runner.invoke(main, [
        '--commit-style', 'simple',
        '--path', str(git_repo)
    ])
    assert result.exit_code == 0
    
    # Test invalid style
    result = cli_runner.invoke(main, [
        '--commit-style', 'invalid',
        '--path', str(git_repo)
    ])
    assert result.exit_code != 0

def test_log_file_option(cli_runner, git_repo, mock_analyzer, mock_committer):
    """Test the --log-file option."""
    log_file = git_repo / "test.log"
    
    with patch('gitsmartcommit.cli.FileLogObserver') as mock_observer:
        result = cli_runner.invoke(main, [
            '--log-file', str(log_file),
            '--path', str(git_repo)
        ])
        
        assert result.exit_code == 0
        # Verify FileLogObserver was created with correct path
        mock_observer.assert_called_once_with(str(log_file))
        # Verify observer was added to committer
        mock_committer.return_value.add_observer.assert_any_call(mock_observer.return_value)

def test_invalid_path(cli_runner):
    """Test behavior with invalid repository path."""
    result = cli_runner.invoke(main, ['--path', '/nonexistent/path'])
    assert result.exit_code != 0

def test_keyboard_interrupt(cli_runner, git_repo, mock_analyzer):
    """Test handling of KeyboardInterrupt."""
    mock_analyzer.return_value.analyze_changes.side_effect = KeyboardInterrupt()
    
    result = cli_runner.invoke(main, ['--path', str(git_repo)])
    
    assert "Operation cancelled by user" in result.output
    # Click converts KeyboardInterrupt to exit code 0
    assert result.exit_code == 0

def test_general_exception(cli_runner, git_repo, mock_analyzer):
    """Test handling of general exceptions."""
    mock_analyzer.return_value.analyze_changes.side_effect = Exception("Test error")
    
    result = cli_runner.invoke(main, ['--path', str(git_repo)])
    
    assert result.exit_code != 0
    assert "Error: Test error" in result.output

def test_config_list_default_values(cli_runner, tmp_path):
    """Test --config-list with default values (no config file)."""
    with cli_runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = cli_runner.invoke(main, ['--config-list'])
        
        assert result.exit_code == 0
        assert "Current Configuration Settings" in result.output
        assert "Using default values (no config file found)" in result.output
        
        # Check all default values are displayed
        lines = result.output.splitlines()
        settings = [line.strip() for line in lines if line.strip()]
        
        assert any("main_branch" in line and "main" in line and "default" in line for line in settings)
        assert any("commit_style" in line and "conventional" in line and "default" in line for line in settings)
        assert any("remote_name" in line and "origin" in line and "default" in line for line in settings)
        assert any("auto_push" in line and "False" in line and "default" in line for line in settings)
        assert any("always_log" in line and "False" in line and "default" in line for line in settings)
        assert any("log_file" in line and "None" in line and "default" in line for line in settings)

def test_config_list_custom_values(cli_runner, tmp_path):
    """Test --config-list with custom values from config file."""
    with cli_runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # Create config with custom values
        config = Config(
            main_branch="develop",
            commit_style="simple",
            remote_name="upstream",
            auto_push=True,
            always_log=True,
            log_file="custom.log"
        )
        config.save(Path(td))
        
        result = cli_runner.invoke(main, ['--config-list'])
        
        assert result.exit_code == 0
        assert "Current Configuration Settings" in result.output
        assert "Config file:" in result.output
        
        # Check all custom values are displayed
        lines = result.output.splitlines()
        settings = [line.strip() for line in lines if line.strip()]
        
        assert any("main_branch" in line and "develop" in line and "config" in line for line in settings)
        assert any("commit_style" in line and "simple" in line and "config" in line for line in settings)
        assert any("remote_name" in line and "upstream" in line and "config" in line for line in settings)
        assert any("auto_push" in line and "True" in line and "config" in line for line in settings)
        assert any("always_log" in line and "True" in line and "config" in line for line in settings)
        assert any("log_file" in line and "custom.log" in line and "config" in line for line in settings)

def test_config_list_with_custom_path(cli_runner, tmp_path):
    """Test --config-list with a custom repository path."""
    repo_path = tmp_path / "custom" / "repo"
    repo_path.mkdir(parents=True)
    
    # Create config in custom path
    config = Config(main_branch="custom-main")
    config.save(repo_path)
    
    result = cli_runner.invoke(main, ['--config-list', '--path', str(repo_path)])
    
    assert result.exit_code == 0
    assert "Current Configuration Settings" in result.output
    
    # Check the config file path is displayed
    config_path = str(repo_path / ".gitsmartcommit.toml").replace(os.sep, '/')
    assert "Config file:" in result.output
    # Normalize strings by removing whitespace and newlines
    normalized_output = ''.join(result.output.split())
    normalized_path = ''.join(config_path.split())
    assert normalized_path in normalized_output
    
    # Check the custom value is displayed
    settings = [line.strip() for line in result.output.splitlines() if line.strip()]
    assert any("main_branch" in line and "custom-main" in line and "config" in line for line in settings) 