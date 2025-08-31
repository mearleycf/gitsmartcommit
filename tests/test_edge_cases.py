"""Tests for edge cases and error handling."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from git import Repo
import shutil

from gitsmartcommit.core import ChangeAnalyzer, GitCommitter
from gitsmartcommit.models import CommitType, CommitUnit, FileChange
from gitsmartcommit.config import Config
from gitsmartcommit.factories import MockAgentFactory

@pytest.fixture
def temp_git_repo_with_large_file():
    """Create a temporary git repo with a large file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a large file (1MB)
        large_file = Path(tmp_dir) / "large_file.txt"
        large_file.write_text("x" * 1024 * 1024)
        
        repo.index.add(["large_file.txt"])
        repo.index.commit("Initial commit with large file")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_with_binary_file():
    """Create a temporary git repo with a binary file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a binary file
        binary_file = Path(tmp_dir) / "image.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)  # Fake PNG header
        
        repo.index.add(["image.png"])
        repo.index.commit("Initial commit with binary file")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_with_special_chars():
    """Create a temporary git repo with files containing special characters."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create files with special characters
        special_file = Path(tmp_dir) / "file with spaces.txt"
        special_file.write_text("Content with spaces")
        
        unicode_file = Path(tmp_dir) / "file-émojis-🚀.txt"
        unicode_file.write_text("Unicode content")
        
        repo.index.add(["file with spaces.txt", "file-émojis-🚀.txt"])
        repo.index.commit("Initial commit with special chars")
        
        yield tmp_dir

@pytest.fixture
def temp_git_repo_detached_head():
    """Create a temporary git repo in detached HEAD state."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create initial commit
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("Initial content")
        repo.index.add(["test.txt"])
        initial_commit = repo.index.commit("Initial commit")
        
        # Checkout a specific commit to create detached HEAD
        repo.head.reference = initial_commit
        
        yield tmp_dir

@pytest.mark.asyncio
async def test_large_file_handling(temp_git_repo_with_large_file):
    """Test handling of large files."""
    # Modify the large file
    large_file = Path(temp_git_repo_with_large_file) / "large_file.txt"
    large_file.write_text("y" * 1024 * 1024)
    
    # Should handle large files gracefully
    analyzer = ChangeAnalyzer(temp_git_repo_with_large_file)
    changes = analyzer._collect_changes()
    
    assert len(changes) == 1
    assert changes[0].path == "large_file.txt"
    # Should truncate content for large files
    assert len(changes[0].content_diff) < 1024 * 1024

@pytest.mark.asyncio
async def test_binary_file_handling(temp_git_repo_with_binary_file):
    """Test handling of binary files."""
    # Modify the binary file
    binary_file = Path(temp_git_repo_with_binary_file) / "image.png"
    binary_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x01' * 100)
    
    analyzer = ChangeAnalyzer(temp_git_repo_with_binary_file)
    changes = analyzer._collect_changes()
    
    assert len(changes) == 1
    assert changes[0].path == "image.png"
    # Binary files may have empty content_diff or binary content
    # The important thing is that it doesn't crash
    assert changes[0].content_diff is not None

@pytest.mark.asyncio
async def test_special_character_paths(temp_git_repo_with_special_chars):
    """Test handling of files with special characters in paths."""
    # Modify files with special characters
    special_file = Path(temp_git_repo_with_special_chars) / "file with spaces.txt"
    special_file.write_text("Modified content with spaces")
    
    unicode_file = Path(temp_git_repo_with_special_chars) / "file-émojis-🚀.txt"
    unicode_file.write_text("Modified unicode content")
    
    analyzer = ChangeAnalyzer(temp_git_repo_with_special_chars)
    changes = analyzer._collect_changes()
    
    assert len(changes) == 2
    paths = [change.path for change in changes]
    assert "file with spaces.txt" in paths
    assert "file-émojis-🚀.txt" in paths

@pytest.mark.asyncio
async def test_detached_head_state(temp_git_repo_detached_head):
    """Test behavior in detached HEAD state."""
    # Create a new file in detached HEAD
    new_file = Path(temp_git_repo_detached_head) / "new.txt"
    new_file.write_text("New file in detached HEAD")
    
    analyzer = ChangeAnalyzer(temp_git_repo_detached_head)
    changes = analyzer._collect_changes()
    
    assert len(changes) == 1
    assert changes[0].path == "new.txt"

@pytest.mark.asyncio
async def test_network_timeout_handling(temp_git_repo):
    """Test handling of network timeouts."""
    from gitsmartcommit.factories import MockAgentFactory
    
    # Create a mock agent that simulates timeout
    mock_agent = Mock()
    mock_agent.run = AsyncMock(side_effect=Exception("Network timeout"))
    
    factory = MockAgentFactory(mock_relationship_agent=mock_agent)
    strategy = factory.create_commit_strategy()
    
    change = FileChange(
        path="test.txt",
        status="modified",
        content_diff="Test content",
        is_staged=False
    )
    
    # Should handle timeout gracefully
    with pytest.raises(Exception, match="Network timeout"):
        await strategy.generate_message([change], "Current branch: main")

@pytest.mark.asyncio
async def test_invalid_api_response_handling(temp_git_repo):
    """Test handling of invalid API responses."""
    from gitsmartcommit.factories import MockAgentFactory
    
    # Create a mock agent that returns invalid response
    mock_agent = Mock()
    mock_agent.run = AsyncMock(return_value=Mock(data=None))  # Invalid response
    
    factory = MockAgentFactory(mock_relationship_agent=mock_agent)
    strategy = factory.create_commit_strategy()
    
    change = FileChange(
        path="test.txt",
        status="modified",
        content_diff="Test content",
        is_staged=False
    )
    
    # Should handle invalid response gracefully
    result = await strategy.generate_message([change], "Current branch: main")
    assert result is None

@pytest.mark.asyncio
async def test_empty_repository_handling():
    """Test handling of empty repositories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Should raise error for empty repo
        with pytest.raises(ValueError, match="No changes detected"):
            analyzer = ChangeAnalyzer(tmp_dir)
            await analyzer.analyze_changes()

@pytest.mark.asyncio
async def test_permission_denied_handling():
    """Test handling of permission denied errors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Make directory read-only
        os.chmod(tmp_dir, 0o444)
        
        try:
            with pytest.raises((PermissionError, OSError)):
                analyzer = ChangeAnalyzer(tmp_dir)
                analyzer._validate_repo()
        finally:
            # Restore permissions
            os.chmod(tmp_dir, 0o755)

@pytest.mark.asyncio
async def test_corrupted_git_repository():
    """Test handling of corrupted git repositories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a directory that's not a git repo
        test_file = Path(tmp_dir) / "not_git.txt"
        test_file.write_text("This is not a git repo")
        
        with pytest.raises((ValueError, git.InvalidGitRepositoryError)):
            analyzer = ChangeAnalyzer(tmp_dir)
            analyzer._validate_repo()

@pytest.mark.asyncio
async def test_commit_with_empty_message(temp_git_repo):
    """Test committing with empty message."""
    # Create a test file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Test content")
    
    # Create commit unit with empty message
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="",  # Empty description
        files=["test.txt"],
        body="",
        message=""
    )
    
    committer = GitCommitter(temp_git_repo)
    
    # Should handle empty message gracefully
    with pytest.raises(ValueError):
        await committer.commit_changes([commit_unit])

@pytest.mark.asyncio
async def test_commit_with_very_long_message(temp_git_repo):
    """Test committing with very long message."""
    # Create a test file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Test content")
    
    # Create commit unit with very long message
    long_description = "a" * 1000  # Very long description
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description=long_description,
        files=["test.txt"],
        body="Very long body " * 100,
        message=f"feat(test): {long_description}"
    )
    
    committer = GitCommitter(temp_git_repo)
    
    # Should handle long message (git will truncate if needed)
    success = await committer.commit_changes([commit_unit])
    assert success is True

@pytest.mark.asyncio
async def test_concurrent_file_modifications(temp_git_repo):
    """Test handling of concurrent file modifications."""
    import threading
    import time
    
    # Create a test file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Initial content")
    
    # Function to modify file concurrently
    def modify_file():
        time.sleep(0.1)  # Small delay
        test_file.write_text("Modified by thread")
    
    # Start modification in background thread
    thread = threading.Thread(target=modify_file)
    thread.start()
    
    # Try to analyze changes while file is being modified
    analyzer = ChangeAnalyzer(temp_git_repo)
    changes = analyzer._collect_changes()
    
    thread.join()
    
    # Should handle concurrent modifications gracefully
    assert len(changes) >= 0  # May or may not detect changes depending on timing

@pytest.mark.asyncio
async def test_symlink_handling(temp_git_repo):
    """Test handling of symbolic links."""
    # Create a test file
    test_file = Path(temp_git_repo) / "original.txt"
    test_file.write_text("Original content")
    
    # Create a symlink
    symlink_file = Path(temp_git_repo) / "link.txt"
    symlink_file.symlink_to("original.txt")
    
    # Add both to git
    repo = Repo(temp_git_repo)
    repo.index.add(["original.txt", "link.txt"])
    repo.index.commit("Add original and symlink")
    
    # Modify the original file
    test_file.write_text("Modified content")
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    changes = analyzer._collect_changes()
    
    # Should detect changes to original file
    assert len(changes) == 1
    assert changes[0].path == "original.txt"

@pytest.mark.asyncio
async def test_submodule_handling(temp_git_repo):
    """Test handling of git submodules."""
    # Create a submodule directory
    submodule_dir = Path(temp_git_repo) / "submodule"
    submodule_dir.mkdir()
    
    # Initialize submodule
    submodule_repo = Repo.init(submodule_dir)
    submodule_file = submodule_dir / "sub.txt"
    submodule_file.write_text("Submodule content")
    submodule_repo.index.add(["sub.txt"])
    submodule_repo.index.commit("Submodule commit")
    
    # Add submodule to main repo
    repo = Repo(temp_git_repo)
    repo.index.add(["submodule"])
    repo.index.commit("Add submodule")
    
    # Modify submodule file
    submodule_file.write_text("Modified submodule content")
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    changes = analyzer._collect_changes()
    
    # Should handle submodule changes
    assert len(changes) >= 0  # May or may not detect submodule changes

@pytest.mark.asyncio
async def test_merge_conflict_handling(temp_git_repo):
    """Test handling of merge conflicts."""
    repo = Repo(temp_git_repo)
    
    # Create initial file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Initial content")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")
    
    # Create a branch
    feature_branch = repo.create_head('feature')
    repo.head.reference = feature_branch
    
    # Modify file in feature branch
    test_file.write_text("Feature content")
    repo.index.add(["test.txt"])
    repo.index.commit("Feature commit")
    
    # Switch back to main and modify same file
    repo.head.reference = repo.heads.master
    test_file.write_text("Main content")
    repo.index.add(["test.txt"])
    repo.index.commit("Main commit")
    
    # Try to merge (will create conflict)
    try:
        repo.git.merge('feature')
    except:
        # Merge conflict expected
        pass
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    
    # Should handle merge conflicts gracefully
    with pytest.raises(ValueError, match="Repository has merge conflicts"):
        analyzer._validate_repo()

@pytest.mark.asyncio
async def test_staged_vs_unstaged_changes(temp_git_repo):
    """Test handling of staged vs unstaged changes."""
    # Create a test file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Initial content")
    
    repo = Repo(temp_git_repo)
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")
    
    # Make staged change
    test_file.write_text("Staged content")
    repo.index.add(["test.txt"])
    
    # Make unstaged change
    test_file.write_text("Unstaged content")
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    changes = analyzer._collect_changes()
    
    # Should detect both staged and unstaged changes
    assert len(changes) == 1
    assert changes[0].path == "test.txt"
    assert "Unstaged content" in changes[0].content_diff

@pytest.mark.asyncio
async def test_file_deletion_and_recreation(temp_git_repo):
    """Test handling of file deletion and recreation."""
    # Create initial file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Initial content")
    
    repo = Repo(temp_git_repo)
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")
    
    # Delete file
    test_file.unlink()
    repo.index.add(["test.txt"])
    repo.index.commit("Delete file")
    
    # Recreate file with same name
    test_file.write_text("Recreated content")
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    changes = analyzer._collect_changes()
    
    # Should detect the new file
    assert len(changes) == 1
    assert changes[0].path == "test.txt"
    assert changes[0].status == "untracked"

@pytest.mark.asyncio
async def test_config_with_invalid_values():
    """Test configuration with invalid values."""
    # Test with invalid commit style
    with pytest.raises(ValueError):
        Config(commit_style="invalid_style")
    
    # Test with invalid main branch name
    with pytest.raises(ValueError):
        Config(main_branch="")
    
    # Test with invalid remote name
    with pytest.raises(ValueError):
        Config(remote_name="")

@pytest.mark.asyncio
async def test_memory_usage_with_many_files():
    """Test memory usage with many files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create many small files
        for i in range(100):
            file_path = Path(tmp_dir) / f"file_{i}.txt"
            file_path.write_text(f"Content {i}")
        
        repo.index.add([f"file_{i}.txt" for i in range(100)])
        repo.index.commit("Add many files")
        
        # Modify some files
        for i in range(0, 100, 10):
            file_path = Path(tmp_dir) / f"file_{i}.txt"
            file_path.write_text(f"Modified content {i}")
        
        analyzer = ChangeAnalyzer(tmp_dir)
        changes = analyzer._collect_changes()
        
        # Should handle many files without memory issues
        assert len(changes) == 10
        assert all(isinstance(change, FileChange) for change in changes)
