import pytest
import tempfile
from pathlib import Path
from git import Repo
import os
import shutil

pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Initialize git repo
        repo = Repo.init(tmp_dir)
        
        # Create a test file
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("Initial content")
        
        # Initial commit
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_with_large_file():
    """Create a temporary git repository with a large file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a large file (1MB)
        large_file = Path(tmp_dir) / "large_file.txt"
        large_content = "x" * (1024 * 1024)  # 1MB
        large_file.write_text(large_content)
        
        repo.index.add(["large_file.txt"])
        repo.index.commit("Add large file")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_with_binary_file():
    """Create a temporary git repository with a binary file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a binary file
        binary_file = Path(tmp_dir) / "image.png"
        binary_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Fake PNG header
        binary_file.write_bytes(binary_content)
        
        repo.index.add(["image.png"])
        repo.index.commit("Add binary file")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_with_special_chars():
    """Create a temporary git repository with special character filenames."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create files with special characters
        special_file = Path(tmp_dir) / "file with spaces.txt"
        special_file.write_text("Content with spaces")
        
        unicode_file = Path(tmp_dir) / "file-émojis-🚀.txt"
        unicode_file.write_text("Unicode content")
        
        repo.index.add(["file with spaces.txt", "file-émojis-🚀.txt"])
        repo.index.commit("Add special character files")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_detached_head():
    """Create a temporary git repository in detached HEAD state."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create initial file
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("Initial content")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        # Create a branch and switch to it
        repo.create_head('feature')
        repo.head.reference = repo.heads.feature
        
        # Make a commit on the branch
        test_file.write_text("Feature content")
        repo.index.add(["test.txt"])
        repo.index.commit("Feature commit")
        
        # Switch to detached HEAD
        repo.head.reference = repo.head.commit
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_with_deleted_file():
    """Create a temporary git repository with a file ready to be deleted."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a file that will be deleted during the test
        test_file = Path(tmp_dir) / "to_delete.txt"
        test_file.write_text("Content to delete")
        repo.index.add(["to_delete.txt"])
        repo.index.commit("Add file to delete")
        
        # The file exists but is not staged for deletion yet
        # The test will handle the deletion and commit
        
        yield tmp_dir

@pytest.fixture
def mock_environment(monkeypatch):
    """Mock environment variables for testing."""
    # Mock API keys
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("HF_HUB_LOCAL_DIR_AUTO_SYMLINK_THRESHOLD", "5242880")  # 5MB
    
    # Mock other environment variables
    monkeypatch.setenv("GITSMARTCOMMIT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("GITSMARTCOMMIT_LOG_FILE", "test.log")
    
    yield

@pytest.fixture
def mock_api_responses(monkeypatch):
    """Mock API responses for testing."""
    # Mock successful API responses
    mock_response = type('MockResponse', (), {
        'data': type('MockData', (), {
            'content': [type('MockContent', (), {
                'text': 'feat(test): test commit message'
            })()]
        })()
    })()
    
    return mock_response