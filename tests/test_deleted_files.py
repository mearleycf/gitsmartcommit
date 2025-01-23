import pytest
import asyncio
from pathlib import Path
import tempfile
import os
from git import Repo
from gitsmartcommit.core import GitCommitter, CommitUnit, CommitType

@pytest.fixture
def temp_git_repo_with_deleted_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Initialize git repo
        repo = Repo.init(tmp_dir)
        
        # Create a test file that will be deleted
        test_file = Path(tmp_dir) / "to_delete.txt"
        test_file.write_text("Content to be deleted")
        
        # Initial commit with the file
        repo.index.add(["to_delete.txt"])
        repo.index.commit("Initial commit")
        
        # Delete the file and stage the deletion
        os.remove(test_file)
        repo.git.rm("--force", "to_delete.txt")
        
        yield tmp_dir

@pytest.mark.asyncio
async def test_commit_deleted_file(temp_git_repo_with_deleted_file):
    # Create a commit unit for the deleted file
    commit_unit = CommitUnit(
        type=CommitType.CHORE,
        scope="cleanup",
        description="remove unused file",
        files=["to_delete.txt"],
        body="Removing file that is no longer needed"
    )
    
    # Commit the deletion
    committer = GitCommitter(temp_git_repo_with_deleted_file)
    success = await committer.commit_changes([commit_unit])
    
    assert success is True
    
    # Verify the file is deleted and committed
    repo = Repo(temp_git_repo_with_deleted_file)
    latest_commit = repo.head.commit
    assert latest_commit.message.startswith("chore(cleanup): remove unused file")
    assert "to_delete.txt" not in repo.head.commit.tree
    
    # Verify the file no longer exists in the working directory
    deleted_file = Path(temp_git_repo_with_deleted_file) / "to_delete.txt"
    assert not deleted_file.exists()
    
    # Verify the file is not in the git index
    assert "to_delete.txt" not in repo.index.entries