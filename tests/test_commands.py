"""Tests for git commands."""
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from git import Repo

from gitsmartcommit.commands import GitCommand, CommitCommand, PushCommand
from gitsmartcommit.models import CommitType, CommitUnit
from gitsmartcommit.observers import GitOperationObserver
from .test_core import temp_git_repo

@pytest.mark.asyncio
async def test_commit_command(temp_git_repo):
    """Test creating and undoing a commit."""
    # Create a test file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Test content")
    
    # Create a commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body",
        message="feat(test): test commit"
    )
    
    # Create and execute commit command
    repo = Repo(temp_git_repo)
    command = CommitCommand(repo, commit_unit)
    success = await command.execute()
    assert success is True
    
    # Verify commit was created
    assert len(list(repo.iter_commits())) > 1  # Initial commit + our commit
    latest_commit = repo.head.commit
    assert latest_commit.message.startswith("feat(test): test commit")
    
    # Test undo
    success = await command.undo()
    assert success is True
    assert len(list(repo.iter_commits())) == 1  # Back to just initial commit

@pytest.mark.asyncio
async def test_push_command_no_remote(temp_git_repo):
    """Test pushing when no remote is configured."""
    # Create a test file and commit
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Test content")
    
    repo = Repo(temp_git_repo)
    repo.index.add(["test.txt"])
    repo.index.commit("test commit")
    
    # Try to push
    command = PushCommand(repo)
    success = await command.execute()
    assert success is False  # Should fail since there's no remote

@pytest.mark.asyncio
async def test_command_observers(temp_git_repo):
    """Test that commands notify observers correctly."""
    # Create mock observer
    mock_observer = Mock(spec=GitOperationObserver)
    mock_observer.on_commit_created = AsyncMock()
    mock_observer.on_push_completed = AsyncMock()
    
    # Create a test file
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Test content")
    
    # Create a commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body",
        message="feat(test): test commit"
    )
    
    # Create and execute commit command with observer
    repo = Repo(temp_git_repo)
    commit_command = CommitCommand(repo, commit_unit)
    commit_command.add_observer(mock_observer)
    
    success = await commit_command.execute()
    assert success is True
    mock_observer.on_commit_created.assert_called_once_with(commit_unit)
    
    # Test push command with observer
    push_command = PushCommand(repo)
    push_command.add_observer(mock_observer)
    
    success = await push_command.execute()
    assert success is False  # No remote configured
    mock_observer.on_push_completed.assert_called_once_with(False)

@pytest.mark.asyncio
async def test_command_history(temp_git_repo):
    """Test command history and undo functionality."""
    # Create test files
    test_file1 = Path(temp_git_repo) / "test1.txt"
    test_file1.write_text("Test content 1")
    
    test_file2 = Path(temp_git_repo) / "test2.txt"
    test_file2.write_text("Test content 2")
    
    repo = Repo(temp_git_repo)
    
    # Create commit units
    commit_unit1 = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="first commit",
        files=["test1.txt"],
        body="First test commit",
        message="feat(test): first commit"
    )
    
    commit_unit2 = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="second commit",
        files=["test2.txt"],
        body="Second test commit",
        message="feat(test): second commit"
    )
    
    # Create and execute commands
    command1 = CommitCommand(repo, commit_unit1)
    success = await command1.execute()
    assert success is True
    
    command2 = CommitCommand(repo, commit_unit2)
    success = await command2.execute()
    assert success is True
    
    # Verify both commits exist
    commits = list(repo.iter_commits())
    assert len(commits) == 3  # Initial + 2 commits
    assert commits[0].message.startswith("feat(test): second commit")
    assert commits[1].message.startswith("feat(test): first commit")
    
    # Undo second commit
    success = await command2.undo()
    assert success is True
    
    # Verify only first commit remains
    commits = list(repo.iter_commits())
    assert len(commits) == 2  # Initial + 1 commit
    assert commits[0].message.startswith("feat(test): first commit") 