"""Tests for handling deleted files."""
import pytest
from pathlib import Path
from git import Repo
import tempfile
import os

from gitsmartcommit.core import GitCommitter
from gitsmartcommit.models import CommitType, CommitUnit

@pytest.mark.asyncio
async def test_commit_deleted_file(temp_git_repo_with_deleted_file):
    # Delete the file first
    deleted_file = Path(temp_git_repo_with_deleted_file) / "to_delete.txt"
    deleted_file.unlink()
    
    # Stage the deletion
    repo = Repo(temp_git_repo_with_deleted_file)
    repo.index.remove(["to_delete.txt"])
    
    # Create a commit unit for the deleted file
    commit_unit = CommitUnit(
        type=CommitType.CHORE,
        scope="cleanup",
        description="remove unused file",
        files=["to_delete.txt"],
        body="Removing file that is no longer needed",
        message="chore(cleanup): remove unused file"
    )
    
    # Initialize committer and create commit
    committer = GitCommitter(temp_git_repo_with_deleted_file)
    success = await committer.commit_changes([commit_unit])
    assert success is True
    
    # Verify commit was created
    repo = Repo(temp_git_repo_with_deleted_file)
    assert len(list(repo.iter_commits())) > 1  # Initial commit + our commit
    
    # Verify the file is deleted and committed
    latest_commit = repo.head.commit
    assert latest_commit.message.startswith("chore(cleanup): remove unused file")
    assert "to_delete.txt" not in repo.head.commit.tree
    
    # Verify the file no longer exists in the working directory
    deleted_file = Path(temp_git_repo_with_deleted_file) / "to_delete.txt"
    assert not deleted_file.exists()
    
    # Verify the file is not in the git index
    assert "to_delete.txt" not in repo.index.entries